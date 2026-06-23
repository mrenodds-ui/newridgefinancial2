import type { Meta, StoryObj } from "@storybook/react";

import { DashboardCard } from "../components/DashboardCard";

const meta: Meta<typeof DashboardCard> = {
  title: "Components/DashboardCard",
  component: DashboardCard,
  tags: ["autodocs"],
};
export default meta;

type Story = StoryObj<typeof DashboardCard>;

export const Gold: Story = {
  args: {
    title: "Production Trend",
    accent: "gold",
    children: <p>Chart content goes here.</p>,
  },
};

export const Green: Story = {
  args: {
    title: "Collections Trend",
    accent: "green",
    children: <p>Chart content goes here.</p>,
  },
};

export const Rust: Story = {
  args: {
    title: "Claim Aging",
    accent: "rust",
    children: <p>Aging breakdown goes here.</p>,
  },
};

export const Slate: Story = {
  args: {
    title: "Practice Central Delta",
    accent: "slate",
    children: <p>Delta metrics go here.</p>,
  },
};

export const Default: Story = {
  args: { title: "Default Card", children: <p>No accent specified.</p> },
};
