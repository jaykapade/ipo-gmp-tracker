import { auth, signIn, signOut } from "@/auth";

const buttonClass =
  "h-8 rounded-md border border-border px-3 text-xs font-medium text-muted-foreground transition-colors hover:bg-muted hover:text-foreground";

export function SignInButton({ label = "Sign in with Google" }: { label?: string }) {
  return (
    <form
      action={async () => {
        "use server";
        await signIn("google");
      }}
    >
      <button type="submit" className={buttonClass}>
        {label}
      </button>
    </form>
  );
}

/** Header sign-in / sign-out. Reads the session, so render it inside Suspense. */
export async function UserMenu() {
  const user = (await auth())?.user;
  if (!user) return <SignInButton label="Sign in" />;

  return (
    <form
      action={async () => {
        "use server";
        await signOut();
      }}
      className="flex items-center gap-2"
    >
      <span className="hidden max-w-40 truncate text-xs text-muted-foreground sm:inline">
        {user.email}
      </span>
      <button type="submit" className={buttonClass}>
        Sign out
      </button>
    </form>
  );
}
