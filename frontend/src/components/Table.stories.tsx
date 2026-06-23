import type { Meta, StoryObj } from "@storybook/react";
import React from "react";

const Table = () => (
  <table style={{ borderCollapse: "collapse", width: 400 }}>
    <thead>
      <tr>
        <th style={{ border: "1px solid #bbb", padding: 8 }}>Name</th>
        <th style={{ border: "1px solid #bbb", padding: 8 }}>Value</th>
      </tr>
    </thead>
    <tbody>
      <tr>
        <td style={{ border: "1px solid #bbb", padding: 8 }}>Alpha</td>
        <td style={{ border: "1px solid #bbb", padding: 8 }}>123</td>
      </tr>
      <tr>
        <td style={{ border: "1px solid #bbb", padding: 8 }}>Beta</td>
        <td style={{ border: "1px solid #bbb", padding: 8 }}>456</td>
      </tr>
    </tbody>
  </table>
);

const meta: Meta<typeof Table> = {
  title: "Components/Table",
  component: Table,
  tags: ["autodocs"],
};
export default meta;

type Story = StoryObj<typeof Table>;

export const Default: Story = {
  render: () => <Table />,
};
