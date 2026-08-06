import { Section } from "@/components/ui/primitives";
import { ProfileHeader } from "@/components/dashboard/ProfileHeader";
import { ResilienceVerdict } from "@/components/dashboard/ResilienceVerdict";
import { SurvivalTimeline } from "@/components/dashboard/SurvivalTimeline";
import { ShockBuilder } from "@/components/dashboard/ShockBuilder";
import { ShockWaterfall } from "@/components/dashboard/ShockWaterfall";
import { VulnerabilityDrivers } from "@/components/dashboard/VulnerabilityDrivers";
import { ObligationStack } from "@/components/dashboard/ObligationStack";
import { RecoveryComparison } from "@/components/dashboard/RecoveryComparison";
import { ScenarioComparison } from "@/components/dashboard/ScenarioComparison";
import { CompoundMatrix } from "@/components/dashboard/CompoundMatrix";
import { AssumptionsPanel } from "@/components/dashboard/AssumptionsPanel";

export default function Home() {
  return (
    <>
      <ProfileHeader />

      <main className="mx-auto flex w-full max-w-6xl flex-col gap-16 px-5 py-10 sm:px-8 sm:py-14">
        <Section
          index="01"
          eyebrow="The verdict"
          title="What this budget can withstand"
          id="verdict"
        >
          <ResilienceVerdict />
        </Section>

        <Section
          index="02"
          eyebrow="Survival timeline"
          title="Where it holds, and where it gives"
          lede="Cash and credit are tracked separately — credit delays the failure, it does not prevent it. Both exhaustion points are marked."
          id="timeline"
        >
          <SurvivalTimeline />
        </Section>

        <Section
          index="03"
          eyebrow="Shock builder"
          title="Stack the emergencies"
          lede="Two are active in this run. The library is ordered by how often US households actually report each event."
          id="shocks"
        >
          <ShockBuilder />
        </Section>

        <Section
          index="04"
          eyebrow="Why it breaks"
          title="The layoff is survivable. The combination is not."
          lede="A $2,400 repair would be a nuisance in a normal month. Landing in month 3 of an income loss, it is the difference between recovering and missing a payment."
          id="why"
        >
          <div className="flex flex-col gap-4">
            <div className="grid gap-4 lg:grid-cols-[minmax(0,1fr)_minmax(0,1fr)]">
              <ShockWaterfall />
              <VulnerabilityDrivers />
            </div>
            <ScenarioComparison />
            <div className="grid gap-4 lg:grid-cols-[minmax(0,1fr)_minmax(0,1fr)]">
              <ObligationStack />
              <CompoundMatrix />
            </div>
          </div>
        </Section>

        <Section
          index="05"
          eyebrow="How to improve"
          title="What actually moves the breaking point"
          lede="Ranked by effect on the one number that matters — how long until a required payment cannot be made."
          id="improve"
        >
          <RecoveryComparison />
        </Section>

        <Section
          index="06"
          eyebrow="Show your work"
          title="Every number, traceable"
          lede="The simulation is deterministic. If you disagree with an assumption, change it and the whole page changes with it."
          id="assumptions"
        >
          <AssumptionsPanel />
        </Section>
      </main>

      <footer className="border-t border-line">
        <div className="mx-auto flex max-w-6xl flex-wrap items-center justify-between gap-3 px-5 py-6 text-[12px] text-ink-3 sm:px-8">
          <span>
            BreakPoint — short- and medium-term financial resilience under compound emergencies
          </span>
          <span className="tnum">
            Demo data · Maya Restrepo is fictional
          </span>
        </div>
      </footer>
    </>
  );
}
