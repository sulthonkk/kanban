import { afterEach, beforeEach, describe, expect, it, vi } from "vitest";
import { cleanup, render, screen, waitFor } from "@testing-library/react";
import userEvent from "@testing-library/user-event";
import { AIChatSidebar } from "@/components/AIChatSidebar";
import { ChatMessage } from "@/lib/chat";

afterEach(() => cleanup());

const baseProps = {
  open: true,
  onClose: () => {},
  onSend: () => {},
};

describe("AIChatSidebar", () => {
  beforeEach(() => {
    vi.clearAllMocks();
  });

  it("renders the sidebar when open", () => {
    render(<AIChatSidebar {...baseProps} messages={[]} loading={false} error={null} />);
    expect(screen.getByRole("heading", { name: "Ask Momentum AI" })).toBeTruthy();
    expect(screen.getByLabelText("Message Momentum AI")).toBeTruthy();
    expect(screen.getByRole("button", { name: "Send" })).toBeTruthy();
  });

  it("is hidden from the a11y tree when closed", () => {
    render(<AIChatSidebar {...baseProps} open={false} messages={[]} loading={false} error={null} />);
    expect(screen.getByLabelText("AI assistant").getAttribute("aria-hidden")).toBe("true");
  });

  it("renders existing messages with user and assistant roles", () => {
    const messages: ChatMessage[] = [
      { id: "u-1", role: "user", content: "Create a deploy task" },
      { id: "a-1", role: "assistant", content: "I created the deployment task." },
    ];
    render(<AIChatSidebar {...baseProps} messages={messages} loading={false} error={null} />);
    expect(screen.getByText("Create a deploy task")).toBeTruthy();
    expect(screen.getByText("I created the deployment task.")).toBeTruthy();
    expect(screen.getAllByText("You")).toHaveLength(1);
    expect(screen.getAllByText("AI")).toHaveLength(1);
  });

  it("shows a placeholder when there are no messages", () => {
    render(<AIChatSidebar {...baseProps} messages={[]} loading={false} error={null} />);
    expect(screen.getByText(/Ask me to create, move, or delete cards/i)).toBeTruthy();
  });

  it("calls onSend when the Send button is clicked with a non-empty message", async () => {
    const onSend = vi.fn();
    render(<AIChatSidebar {...baseProps} messages={[]} loading={false} error={null} onSend={onSend} />);
    const user = userEvent.setup();
    await user.type(screen.getByLabelText("Message Momentum AI"), "add a card to Ready");
    await user.click(screen.getByRole("button", { name: "Send" }));
    expect(onSend).toHaveBeenCalledWith("add a card to Ready");
  });

  it("calls onSend when Enter is pressed (without Shift)", async () => {
    const onSend = vi.fn();
    render(<AIChatSidebar {...baseProps} messages={[]} loading={false} error={null} onSend={onSend} />);
    const user = userEvent.setup();
    const input = screen.getByLabelText("Message Momentum AI") as HTMLTextAreaElement;
    await user.type(input, "rename Backlog to Ideas");
    await user.keyboard("{Enter}");
    expect(onSend).toHaveBeenCalledWith("rename Backlog to Ideas");
  });

  it("does not call onSend on Shift+Enter (lets the textarea insert a newline)", async () => {
    const onSend = vi.fn();
    render(<AIChatSidebar {...baseProps} messages={[]} loading={false} error={null} onSend={onSend} />);
    const user = userEvent.setup();
    await user.type(screen.getByLabelText("Message Momentum AI"), "first line");
    await user.keyboard("{Shift>}{Enter}{/Shift}");
    expect(onSend).not.toHaveBeenCalled();
  });

  it("disables the send button while loading", () => {
    render(<AIChatSidebar {...baseProps} messages={[]} loading={true} error={null} />);
    expect((screen.getByRole("button", { name: "Send" }) as HTMLButtonElement).disabled).toBe(true);
  });

  it("disables the send button when the draft is empty", () => {
    render(<AIChatSidebar {...baseProps} messages={[]} loading={false} error={null} />);
    expect((screen.getByRole("button", { name: "Send" }) as HTMLButtonElement).disabled).toBe(true);
  });

  it("shows a thinking indicator while loading", () => {
    render(<AIChatSidebar {...baseProps} messages={[]} loading={true} error={null} />);
    expect(screen.getByText("Thinking…")).toBeTruthy();
  });

  it("renders the error message when an error is provided", () => {
    render(<AIChatSidebar {...baseProps} messages={[]} loading={false} error={"AI request failed"} />);
    expect(screen.getByRole("alert").textContent).toContain("AI request failed");
  });

  it("does not double-send if the request is still loading", async () => {
    const onSend = vi.fn();
    render(<AIChatSidebar {...baseProps} messages={[]} loading={true} error={null} onSend={onSend} />);
    const user = userEvent.setup();
    await user.type(screen.getByLabelText("Message Momentum AI"), "second message");
    await user.click(screen.getByRole("button", { name: "Send" }));
    expect(onSend).not.toHaveBeenCalled();
  });

  it("clears the draft after a successful send", async () => {
    const onSend = vi.fn();
    render(<AIChatSidebar {...baseProps} messages={[]} loading={false} error={null} onSend={onSend} />);
    const input = screen.getByLabelText("Message Momentum AI") as HTMLTextAreaElement;
    const user = userEvent.setup();
    await user.type(input, "hello");
    await user.click(screen.getByRole("button", { name: "Send" }));
    await waitFor(() => expect(input.value).toBe(""));
  });

  it("calls onClose when the close button is clicked", async () => {
    const onClose = vi.fn();
    render(<AIChatSidebar {...baseProps} messages={[]} loading={false} error={null} onClose={onClose} />);
    const user = userEvent.setup();
    await user.click(screen.getByLabelText("Close AI assistant"));
    expect(onClose).toHaveBeenCalledTimes(1);
  });
});