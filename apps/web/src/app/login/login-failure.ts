export function loginFailureLocation(error: unknown) {
  void error;
  return "/login?error=invalid_credentials" as const;
}
