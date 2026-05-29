import { clerkMiddleware } from "@clerk/nextjs/server";

// Default Clerk matcher: every route except Next internals and static
// assets goes through Clerk so `auth()` is callable everywhere. Auth is
// NOT enforced here — pages choose whether to gate themselves. `/demo`
// and `/profile/new` both require a signed-in user and render their own
// sign-in prompt when there isn't one.
export default clerkMiddleware();

export const config = {
  matcher: [
    "/((?!_next|[^?]*\\.(?:html?|css|js(?!on)|jpe?g|webp|png|gif|svg|ttf|woff2?|ico|csv|docx?|xlsx?|zip|webmanifest)).*)",
    "/(api|trpc)(.*)",
  ],
};
