import "@testing-library/jest-dom/vitest";
import { act, fireEvent, render, screen, waitFor } from "@testing-library/react";
import { describe, expect, it, vi } from "vitest";

import type { ScreenCode } from "@/lib/screen-catalog";
import { ScreenRuleExperience, screenRuleDefinitions, type ScreenRule, type ScreenRuleBoundary } from "./screen-rule-experiences";

const cases = Object.entries(screenRuleDefinitions) as Array<[ScreenCode, ScreenRule]>;

describe("ScreenRuleExperience", () => {
  it.each(cases)("validates and sends the domain payload for %s", async (code, rule) => {
    const boundary = vi.fn<ScreenRuleBoundary>().mockResolvedValue({ ok: true });
    render(<ScreenRuleExperience boundary={boundary} code={code} />);
    const input = screen.getByLabelText(rule.label);

    fireEvent.click(screen.getByRole("button", { name: rule.action }));
    expect(screen.getByRole("status")).toHaveTextContent(rule.validate(rule.invalidValue)!);
    expect(boundary).not.toHaveBeenCalled();

    fireEvent.change(input, { target: { value: rule.safeValue } });
    fireEvent.click(screen.getByRole("button", { name: rule.action }));
    await waitFor(() => expect(boundary).toHaveBeenCalledWith({ code, operation: rule.operation, payload: rule.payload(rule.safeValue) }));
    expect(screen.getByRole("status")).toHaveTextContent(rule.effect);
  });

  it.each(cases)("exposes loading and preserves the specific value on transport failure for %s", async (code, rule) => {
    let reject!: (reason: Error) => void;
    const boundary = vi.fn<ScreenRuleBoundary>().mockImplementation(() => new Promise((_resolve, rejectPromise) => { reject = rejectPromise; }));
    render(<ScreenRuleExperience boundary={boundary} code={code} />);
    const input = screen.getByLabelText<HTMLInputElement>(rule.label);
    fireEvent.change(input, { target: { value: rule.safeValue } });
    fireEvent.click(screen.getByRole("button", { name: rule.action }));

    expect(screen.getByRole("button", { name: "Processando operacao" })).toBeDisabled();
    expect(screen.getByRole("status")).toHaveTextContent("Validando no servico");
    act(() => reject(new Error("network")));
    await waitFor(() => expect(screen.getByRole("status")).toHaveTextContent("Falha de transporte"));
    expect(input).toHaveValue(rule.inputType === "number" ? Number(rule.safeValue) : rule.safeValue);
  });

  it.each(cases)("renders a service rejection for %s", async (code, rule) => {
    const boundary = vi.fn<ScreenRuleBoundary>().mockResolvedValue({ ok: false, message: `Rejeitada em ${rule.operation}` });
    render(<ScreenRuleExperience boundary={boundary} code={code} />);
    fireEvent.change(screen.getByLabelText(rule.label), { target: { value: rule.safeValue } });
    fireEvent.click(screen.getByRole("button", { name: rule.action }));
    expect(await screen.findByText(`Rejeitada em ${rule.operation}`)).toBeInTheDocument();
  });

  it("covers exactly the 24 remediated screens", () => {
    expect(cases.map(([code]) => code)).toEqual(["T02", "T03", "T09", "T12", "T18", "T19", "T22", "T24", "T25", "T26", "T31", "T34", "T35", "T36", "T37", "T39", "T41", "T43", "T46", "T49", "T50", "T51", "T52", "T53"]);
  });

  it("uses the MSW-compatible HTTP boundary without component changes", async () => {
    const rule = screenRuleDefinitions.T02;
    render(<ScreenRuleExperience code="T02" />);
    fireEvent.change(screen.getByLabelText(rule.label), { target: { value: rule.safeValue } });
    fireEvent.click(screen.getByRole("button", { name: rule.action }));
    expect(await screen.findByText(rule.effect)).toBeInTheDocument();
  });

  it("rejects a past T19 date and malformed T34 attempt pairs", () => {
    expect(screenRuleDefinitions.T19.validate("2020-01-01|Justificativa valida")).toBeTruthy();
    expect(screenRuleDefinitions.T19.validate("2027-99-99|Justificativa valida")).toBeTruthy();
    expect(screenRuleDefinitions.T34.validate("run-7:1,run-7:1")).toBeTruthy();
    expect(screenRuleDefinitions.T34.validate("run-7:01,run-7:1")).toBeTruthy();
    expect(screenRuleDefinitions.T34.validate(":1,:2")).toBeTruthy();
  });
});
