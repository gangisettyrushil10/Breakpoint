/**
 * A small in-memory stand-in for the parts of postgrest-js that
 * `lib/supabase/store.ts` actually uses.
 *
 * It stores rows rather than returning canned responses, because the behaviour
 * worth pinning down is stateful: that appending a turn does not re-insert the
 * previous ones, that an upsert replaces instead of duplicating, that reads come
 * back in insertion order. Canned responses would assert the store called some
 * methods, not that the transcript survives.
 *
 * What it deliberately does NOT model: row-level security. RLS is enforced by
 * Postgres and can only be verified against a real project -- see
 * `docs`/the Phase 2.7 note for the live check that does it.
 */

interface Row {
  [column: string]: unknown;
}

type Op = "select" | "insert" | "upsert" | "delete";

interface Result {
  data: unknown;
  error: unknown;
  count: number | null;
}

class FakeTable {
  rows: Row[] = [];
  nextId = 1;
}

export class FakeSupabase {
  readonly tables = new Map<string, FakeTable>();

  /** Set to make the very next awaited query fail, for error-path tests. */
  failNext: { message: string; code?: string } | null = null;

  private table(name: string): FakeTable {
    let table = this.tables.get(name);
    if (!table) {
      table = new FakeTable();
      this.tables.set(name, table);
    }
    return table;
  }

  rowsIn(name: string): Row[] {
    return this.table(name).rows;
  }

  from(name: string) {
    return new FakeQuery(this, this.table(name));
  }
}

class FakeQuery implements PromiseLike<Result> {
  private op: Op = "select";
  private filters: Array<[string, unknown]> = [];
  private columns = "*";
  private headOnly = false;
  private wantCount = false;
  private singleRow = false;
  private orderColumn: string | null = null;
  private payload: Row | Row[] | null = null;

  constructor(
    private readonly db: FakeSupabase,
    private readonly table: FakeTable
  ) {}

  select(columns = "*", options?: { count?: string; head?: boolean }) {
    // `.select()` after an insert/upsert is a returning clause, not a new query.
    if (this.op === "select") this.op = "select";
    this.columns = columns;
    this.wantCount = options?.count === "exact";
    this.headOnly = options?.head === true;
    return this;
  }

  insert(rows: Row | Row[]) {
    this.op = "insert";
    this.payload = rows;
    return this;
  }

  // The real signature takes an { onConflict } option; the fake always conflicts
  // on user_id, which is the only way the store calls it.
  upsert(rows: Row | Row[]) {
    this.op = "upsert";
    this.payload = rows;
    return this;
  }

  delete() {
    this.op = "delete";
    return this;
  }

  eq(column: string, value: unknown) {
    this.filters.push([column, value]);
    return this;
  }

  // Ascending only, which is the only ordering the store asks for.
  order(column: string) {
    this.orderColumn = column;
    return this;
  }

  single() {
    this.singleRow = true;
    return this;
  }

  private matches(row: Row): boolean {
    return this.filters.every(([column, value]) => row[column] === value);
  }

  private project(row: Row): Row {
    if (this.columns === "*") return { ...row };
    const wanted = this.columns.split(",").map((c) => c.trim());
    const out: Row = {};
    for (const column of wanted) out[column] = row[column];
    return out;
  }

  private run(): Result {
    const failure = this.db.failNext;
    if (failure) {
      this.db.failNext = null;
      return { data: null, error: failure, count: null };
    }

    if (this.op === "insert" || this.op === "upsert") {
      const rows = Array.isArray(this.payload) ? this.payload : [this.payload!];

      for (const row of rows) {
        if (this.op === "upsert") {
          const existing = this.table.rows.findIndex(
            (candidate) => candidate.user_id === row.user_id
          );
          if (existing !== -1) {
            this.table.rows[existing] = { ...this.table.rows[existing], ...row };
            continue;
          }
        }
        this.table.rows.push({ id: this.table.nextId++, ...row });
      }

      return { data: null, error: null, count: null };
    }

    if (this.op === "delete") {
      this.table.rows = this.table.rows.filter((row) => !this.matches(row));
      return { data: null, error: null, count: null };
    }

    let matched = this.table.rows.filter((row) => this.matches(row));

    if (this.orderColumn) {
      const column = this.orderColumn;
      matched = [...matched].sort(
        (a, b) => Number(a[column]) - Number(b[column])
      );
    }

    if (this.headOnly) {
      return { data: null, error: null, count: this.wantCount ? matched.length : null };
    }

    if (this.singleRow) {
      if (matched.length === 0) {
        // The code postgrest returns for "no rows" from .single(), which the
        // store treats as "new account" rather than as a failure.
        return {
          data: null,
          error: { code: "PGRST116", message: "no rows returned" },
          count: null,
        };
      }
      return { data: this.project(matched[0]), error: null, count: null };
    }

    return {
      data: matched.map((row) => this.project(row)),
      error: null,
      count: this.wantCount ? matched.length : null,
    };
  }

  then<TResult1 = Result, TResult2 = never>(
    onfulfilled?: ((value: Result) => TResult1 | PromiseLike<TResult1>) | null,
    onrejected?: ((reason: unknown) => TResult2 | PromiseLike<TResult2>) | null
  ): PromiseLike<TResult1 | TResult2> {
    return Promise.resolve(this.run()).then(onfulfilled, onrejected);
  }
}
