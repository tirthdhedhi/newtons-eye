"use client";

import type { Timeline as TimelineData } from "./types";

export interface TimelineProps {
  timeline: TimelineData;
  currentStep: number;
  playing: boolean;
  onPlay: () => void;
  onPause: () => void;
  onNext: () => void;
  onBack: () => void;
}

/**
 * Step controls for the diagram.
 * TODO(renderer): autoplay using timeline.stepDurationMs, keyboard shortcuts, scrubber.
 */
export default function Timeline({
  timeline,
  currentStep,
  playing,
  onPlay,
  onPause,
  onNext,
  onBack,
}: TimelineProps) {
  const total = timeline.steps.length;
  return (
    <div className="flex items-center gap-2">
      <button type="button" onClick={onBack} disabled={currentStep <= 0}>
        Back
      </button>
      <button type="button" onClick={playing ? onPause : onPlay}>
        {playing ? "Pause" : "Play"}
      </button>
      <button type="button" onClick={onNext} disabled={currentStep >= total - 1}>
        Next
      </button>
      <span>
        {total === 0 ? 0 : currentStep + 1} / {total}
      </span>
    </div>
  );
}
