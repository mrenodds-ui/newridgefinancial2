import type { Meta, StoryObj } from "@storybook/react";
import React from "react";
import { ErrorBoundary } from "./ErrorBoundary";

const meta: Meta<typeof ErrorBoundary> = {
  title: "Components/ErrorBoundary",
  component: ErrorBoundary,
  tags: ["autodocs"],
};
export default meta;

type Story = StoryObj<typeof ErrorBoundary>;

const Bomb = () => {
  throw new Error("Boom!");
};

export const CatchesError: Story = {
  render: () => (
    <ErrorBoundary contextLabel="Test">
      <Bomb />
    </ErrorBoundary>
  ),
};
