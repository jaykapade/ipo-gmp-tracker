/**
 * Google sign-in (Auth.js). Sessions live in an encrypted cookie (no database).
 * Reads AUTH_SECRET, AUTH_GOOGLE_ID and AUTH_GOOGLE_SECRET from the environment.
 */

import NextAuth from "next-auth";
import Google from "next-auth/providers/google";

export const { handlers, auth, signIn, signOut } = NextAuth({
  providers: [Google],
});

/** The signed-in user's Google-verified email, or null. */
export async function currentEmail(): Promise<string | null> {
  return (await auth())?.user?.email ?? null;
}
