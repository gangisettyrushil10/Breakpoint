"use client";

import { Section } from "@/components/ui/primitives";
import { DashboardProvider } from "@/components/dashboard/DashboardProvider";
import { ProfileHeader } from "@/components/dashboard/ProfileHeader";
import { DemoNotice } from "@/components/dashboard/DemoNotice";
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
import { DataFooter } from "@/components/dashboard/DataFooter";

export default function Home() {
  return (
    <DashboardProvider>
      <ProfileHeader />
      <DemoNotice />

      <main className="dashboard-shell mx-auto flex w-full max-w-6xl flex-col gap-14 px-5 py-10 sm:px-8 sm:py-14">
        <Section
          index="01"
          eyebrow="The short answer"
          title="How much bad luck can your money take?"
          id="verdict"
        >
          <ResilienceVerdict />
        </Section>

        <Section
          index="02"
          eyebrow="Interactive stress test"
          title="Stack the setbacks. Watch the budget react."
          lede="Start from a calm month, then add the events you want to test. One-time shocks change survival; permanent budget changes move the baseline score."
          id="shocks"
        >
          <ShockBuilder />
        </Section>

        <Section
          index="03"
          eyebrow="Month by month"
          title="See exactly when the pressure lands"
          lede="Savings and credit stay separate because they run out at different times. Credit can buy time after cash reaches zero, but it cannot make the budget safe."
          id="timeline"
        >
          <SurvivalTimeline />
        </Section>

        <Section
          index="04"
          eyebrow="What would help"
          title="Move the breaking point"
          lede="The engine prices two concrete escape routes: more liquid savings before the shock, or a monthly reduction limited to spending that can actually be paused."
          id="improve"
        >
          <RecoveryComparison />
        </Section>

        <Section
          index="05"
          eyebrow="The reason"
          title="One setback, or several at once"
          lede="A single piece of bad luck is usually survivable. The same setbacks landing close together often are not, because the first one uses up the savings that would have absorbed the second."
          id="why"
          collapsible
          openLabel="Show me why"
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
          index="06"
          eyebrow="Our workings"
          title="Where every number came from"
          lede="Nothing here is guessed or generated. If you disagree with something we assumed, change it and the whole page is worked out again."
          id="assumptions"
          collapsible
          openLabel="Show me the workings"
        >
          <AssumptionsPanel />
        </Section>
      </main>

      <DataFooter />
    </DashboardProvider>
  );
}
