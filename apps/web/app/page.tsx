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

      <main className="mx-auto flex w-full max-w-6xl flex-col gap-16 px-5 py-10 sm:px-8 sm:py-14">
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
          eyebrow="Month by month"
          title="When things would start to go wrong"
          lede="Savings and credit are shown separately, because they run out at different times. A credit card keeps the bills paid for a while after the savings are gone — it buys you time, it does not make you safe."
          id="timeline"
        >
          <SurvivalTimeline />
        </Section>

        <Section
          index="03"
          eyebrow="Try it yourself"
          title="What if these things happened?"
          lede="Turn on the setbacks you want to test and everything on this page is worked out again. They are listed roughly in the order US households actually report them."
          id="shocks"
        >
          <ShockBuilder />
        </Section>

        <Section
          index="04"
          eyebrow="The reason"
          title="One setback, or several at once"
          lede="A single piece of bad luck is usually survivable. The same setbacks landing close together often are not, because the first one uses up the savings that would have absorbed the second."
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
          eyebrow="What would help"
          title="What would actually have made a difference"
          lede="Two ways out, both worked out from exactly how far past the limit things went: money saved up beforehand, or spending stopped each month. If the amount you would need to cut is more than you could realistically cut, we say so instead of pretending."
          id="improve"
        >
          <RecoveryComparison />
        </Section>

        <Section
          index="06"
          eyebrow="Our workings"
          title="Where every number came from"
          lede="Nothing here is guessed or generated. If you disagree with something we assumed, change it and the whole page is worked out again."
          id="assumptions"
        >
          <AssumptionsPanel />
        </Section>
      </main>

      <DataFooter />
    </DashboardProvider>
  );
}
