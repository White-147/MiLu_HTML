export function normalizeMiLuBranding(
  text?: string | null,
): string | undefined {
  if (!text) {
    return text ?? undefined;
  }

  return text.split("CoPaw").join("MiLu").split("copaw").join("milu");
}
