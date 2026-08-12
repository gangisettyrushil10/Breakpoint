"use client";

import { useRouter } from "next/navigation";
import { useState } from "react";
import { useProfile } from "@/components/ProfileProvider";
import { Card } from "@/components/ui/primitives";
import { defaultProfile } from "@/lib/api/mappers";
import {
  JOB_STABILITIES,
  MONEY_GROUPS,
  PAY_FREQUENCIES,
  draftToProfile,
  profileToDraft,
  type Draft,
  type FieldErrors,
} from "@/lib/intake";

export function IntakeForm() {
  const { hydrated } = useProfile();

  // Gate on hydration so the inner form's state initialiser sees the stored
  // profile. Seeding from the demo and then re-seeding would fight the user's
  // typing, so the fix is to not mount until there's something real to seed from.
  if (!hydrated) {
    return (
      <p className="text-[13px] text-ink-3" role="status">
        Loading…
      </p>
    );
  }

  return <IntakeFormFields />;
}

function IntakeFormFields() {
  const router = useRouter();
  const { profile, hasOwnProfile, setProfile } = useProfile();

  const [draft, setDraft] = useState<Draft>(() => profileToDraft(profile));
  const [errors, setErrors] = useState<FieldErrors>({});

  function set(key: string, value: string) {
    setDraft((prev) => ({ ...prev, [key]: value }));
    if (errors[key]) {
      setErrors((prev) => {
        const next = { ...prev };
        delete next[key];
        return next;
      });
    }
  }

  function onSubmit(event: React.FormEvent) {
    event.preventDefault();
    const { profile: next, errors: found } = draftToProfile(draft);

    if (!next) {
      setErrors(found);
      // Move focus to the first problem rather than leaving the user to hunt.
      const first = Object.keys(found)[0];
      document.getElementById(first)?.focus();
      return;
    }

    setProfile(next);
    router.push("/");
  }

  return (
    <form onSubmit={onSubmit} className="flex flex-col gap-8" noValidate>
      <Card>
        <h2 className="text-[15px] font-medium">About you</h2>
        <p className="mt-1 max-w-[62ch] text-[13px] leading-relaxed text-ink-2">
          Location and household don&rsquo;t change the math in this version — they
          label the run, and Phase 3 will use them for local rent data.
        </p>

        <div className="mt-5 grid gap-4 sm:grid-cols-3">
          <TextField
            id="location.city"
            label="City"
            value={draft["location.city"] ?? ""}
            error={errors["location.city"]}
            onChange={(v) => set("location.city", v)}
          />
          <TextField
            id="location.state"
            label="State"
            value={draft["location.state"] ?? ""}
            error={errors["location.state"]}
            onChange={(v) => set("location.state", v.toUpperCase().slice(0, 2))}
            maxLength={2}
          />
          <TextField
            id="location.postalCode"
            label="ZIP code"
            value={draft["location.postalCode"] ?? ""}
            error={errors["location.postalCode"]}
            onChange={(v) => set("location.postalCode", v)}
            inputMode="numeric"
          />
        </div>

        <div className="mt-4 grid gap-4 sm:grid-cols-2">
          <TextField
            id="household.dependents"
            label="Dependents"
            value={draft["household.dependents"] ?? ""}
            error={errors["household.dependents"]}
            onChange={(v) => set("household.dependents", v.replace(/[^\d]/g, ""))}
            inputMode="numeric"
          />
          <SelectField
            id="household.jobStability"
            label="Job stability"
            value={draft["household.jobStability"] ?? "stable"}
            options={JOB_STABILITIES}
            onChange={(v) => set("household.jobStability", v)}
          />
        </div>
      </Card>

      {MONEY_GROUPS.map((group) => (
        <Card key={group.id}>
          <h2 className="text-[15px] font-medium">{group.title}</h2>
          <p className="mt-1 max-w-[62ch] text-[13px] leading-relaxed text-ink-2">
            {group.lede}
          </p>

          <div className="mt-5 grid gap-4 sm:grid-cols-2">
            {group.money.map((field) => (
              <MoneyInput
                key={field.key}
                id={field.key}
                label={field.label}
                hint={field.hint}
                value={draft[field.key] ?? ""}
                error={errors[field.key]}
                onChange={(v) => set(field.key, v)}
              />
            ))}

            {group.id === "income" ? (
              <SelectField
                id="income.payFrequency"
                label="Pay frequency"
                value={draft["income.payFrequency"] ?? "monthly"}
                options={PAY_FREQUENCIES}
                onChange={(v) => set("income.payFrequency", v)}
              />
            ) : null}

            {group.id === "debt" ? (
              <TextField
                id="debt.creditAprBps"
                label="Credit card APR"
                hint="Percent, e.g. 24.99"
                value={draft["debt.creditAprBps"] ?? ""}
                error={errors["debt.creditAprBps"]}
                onChange={(v) => set("debt.creditAprBps", v)}
                inputMode="decimal"
                suffix="%"
              />
            ) : null}
          </div>
        </Card>
      ))}

      <div className="flex flex-wrap items-center gap-3 border-t border-line pt-5">
        <button
          type="submit"
          className="rounded-lg bg-accent px-4 py-2.5 text-[13.5px] font-medium text-bg"
        >
          {hasOwnProfile ? "Save changes" : "Run my stress test"}
        </button>

        <button
          type="button"
          onClick={() => {
            setDraft(profileToDraft(defaultProfile));
            setErrors({});
          }}
          className="rounded-lg border border-line bg-surface-1 px-3.5 py-2.5 text-[13px] text-ink-2 hover:border-line-strong hover:text-ink"
        >
          Fill with the example budget
        </button>

        {Object.keys(errors).length > 0 ? (
          <p role="alert" className="text-[13px] text-critical">
            {Object.keys(errors).length} field
            {Object.keys(errors).length === 1 ? "" : "s"} need attention.
          </p>
        ) : null}
      </div>

      <p className="text-[12px] leading-relaxed text-ink-3">
        Your numbers stay in this browser. They&rsquo;re sent to the simulation engine
        to be calculated, and are never stored on a server.
      </p>
    </form>
  );
}

const fieldClass =
  "w-full rounded-lg border bg-surface-1 px-3 py-2 text-[14px] text-ink placeholder:text-ink-3 focus:outline-none focus:ring-1";

function borderFor(error?: string) {
  return error
    ? "border-critical focus:border-critical focus:ring-critical"
    : "border-line focus:border-line-strong focus:ring-line-strong";
}

function FieldShell({
  id,
  label,
  hint,
  error,
  children,
}: {
  id: string;
  label: string;
  hint?: string;
  error?: string;
  children: React.ReactNode;
}) {
  return (
    <div className="min-w-0">
      <label htmlFor={id} className="block text-[13px] text-ink-2">
        {label}
      </label>
      <div className="mt-1.5">{children}</div>
      {error ? (
        <p id={`${id}-error`} className="mt-1 text-[12px] text-critical">
          {error}
        </p>
      ) : hint ? (
        <p id={`${id}-hint`} className="mt-1 text-[12px] text-ink-3">
          {hint}
        </p>
      ) : null}
    </div>
  );
}

function MoneyInput({
  id,
  label,
  hint,
  value,
  error,
  onChange,
}: {
  id: string;
  label: string;
  hint?: string;
  value: string;
  error?: string;
  onChange: (value: string) => void;
}) {
  return (
    <FieldShell id={id} label={label} hint={hint} error={error}>
      <div className="relative">
        <span
          aria-hidden
          className="pointer-events-none absolute left-3 top-1/2 -translate-y-1/2 text-[14px] text-ink-3"
        >
          $
        </span>
        <input
          id={id}
          name={id}
          type="text"
          inputMode="decimal"
          value={value}
          onChange={(event) => onChange(event.target.value)}
          aria-invalid={error ? true : undefined}
          aria-describedby={error ? `${id}-error` : hint ? `${id}-hint` : undefined}
          className={`tnum pl-7 ${fieldClass} ${borderFor(error)}`}
        />
      </div>
    </FieldShell>
  );
}

function TextField({
  id,
  label,
  hint,
  value,
  error,
  onChange,
  inputMode,
  maxLength,
  suffix,
}: {
  id: string;
  label: string;
  hint?: string;
  value: string;
  error?: string;
  onChange: (value: string) => void;
  inputMode?: "numeric" | "decimal";
  maxLength?: number;
  suffix?: string;
}) {
  return (
    <FieldShell id={id} label={label} hint={hint} error={error}>
      <div className="relative">
        <input
          id={id}
          name={id}
          type="text"
          inputMode={inputMode}
          maxLength={maxLength}
          value={value}
          onChange={(event) => onChange(event.target.value)}
          aria-invalid={error ? true : undefined}
          aria-describedby={error ? `${id}-error` : hint ? `${id}-hint` : undefined}
          className={`${suffix ? "pr-8" : ""} ${fieldClass} ${borderFor(error)}`}
        />
        {suffix ? (
          <span
            aria-hidden
            className="pointer-events-none absolute right-3 top-1/2 -translate-y-1/2 text-[14px] text-ink-3"
          >
            {suffix}
          </span>
        ) : null}
      </div>
    </FieldShell>
  );
}

function SelectField({
  id,
  label,
  value,
  options,
  onChange,
}: {
  id: string;
  label: string;
  value: string;
  options: { value: string; label: string }[];
  onChange: (value: string) => void;
}) {
  return (
    <FieldShell id={id} label={label}>
      <select
        id={id}
        name={id}
        value={value}
        onChange={(event) => onChange(event.target.value)}
        className={`${fieldClass} ${borderFor(undefined)}`}
      >
        {options.map((option) => (
          <option key={option.value} value={option.value}>
            {option.label}
          </option>
        ))}
      </select>
    </FieldShell>
  );
}
