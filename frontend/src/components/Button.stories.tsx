import type { Meta, StoryObj } from "@storybook/react";
import type React from "react";

const Button = (props: React.ButtonHTMLAttributes<HTMLButtonElement>) => (
  <button
    {...props}
    style={{
      padding: "8px 18px",
      borderRadius: 6,
      border: "1px solid #bbb",
      background: "#fff",
      ...props.style,
    }}
  >
    {props.children}
  </button>
);

const meta: Meta<typeof Button> = {
  title: "Components/Button",
  component: Button,
  tags: ["autodocs"],
};
export default meta;

type Story = StoryObj<typeof Button>;

export const Default: Story = {
  args: {
    children: "Button",
  },
};

export const Disabled: Story = {
  args: {
    children: "Disabled",
    disabled: true,
  },
};
