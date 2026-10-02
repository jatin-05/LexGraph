"use client";

import { FormEvent, useEffect, useState } from "react";
import { useRouter } from "next/navigation";
import { getSupabaseClient } from "@/lib/supabase/client";

function BrandMark() {
  return (
    <div className="brand-lockup">
      <span className="brand-mark" aria-hidden="true">
        <svg viewBox="0 0 32 32" fill="none">
          <path d="M8 4.75h10l6 6v16.5H8V4.75Z" />
          <path d="M18 4.75v6h6M12 16h8M12 20h8" />
          <circle cx="9" cy="23" r="3.25" />
          <path d="m7.8 23 1 1 2-2" />
        </svg>
      </span>
      <span>LexGraph</span>
    </div>
  );
}

export function AuthScreen() {
  const router = useRouter();
  const [mode, setMode] = useState<"signin" | "signup">("signin");
  const [email, setEmail] = useState("");
  const [password, setPassword] = useState("");
  const [busy, setBusy] = useState(false);
  const [error, setError] = useState("");
  const [notice, setNotice] = useState("");
  const [configured] = useState(
    Boolean(process.env.NEXT_PUBLIC_SUPABASE_URL && process.env.NEXT_PUBLIC_SUPABASE_ANON_KEY),
  );

  useEffect(() => {
    const supabase = getSupabaseClient();
    if (!supabase) return;

    let mounted = true;
    supabase.auth.getSession().then(({ data }) => {
      if (mounted && data.session) router.replace("/workspace");
    });
    const { data } = supabase.auth.onAuthStateChange((_event, session) => {
      if (session) router.replace("/workspace");
    });
    return () => {
      mounted = false;
      data.subscription.unsubscribe();
    };
  }, [router]);

  async function handleSubmit(event: FormEvent<HTMLFormElement>) {
    event.preventDefault();
    setError("");
    setNotice("");
    const supabase = getSupabaseClient();
    if (!supabase) return;

    setBusy(true);
    const normalizedEmail = email.trim();
    try {
      if (mode === "signin") {
        const { error: authError } = await supabase.auth.signInWithPassword({
          email: normalizedEmail,
          password,
        });
        if (authError) throw authError;
        router.push("/workspace");
      } else {
        const { data, error: authError } = await supabase.auth.signUp({
          email: normalizedEmail,
          password,
        });
        if (authError) throw authError;
        if (data.session) router.push("/workspace");
        else setNotice("Check your email to confirm your account, then sign in.");
      }
    } catch (authError) {
      const message = authError instanceof Error ? authError.message : "Authentication failed.";
      const code =
        typeof authError === "object" && authError !== null && "code" in authError &&
        typeof authError.code === "string"
          ? authError.code
          : "";
      setError(code ? `${message} (${code})` : message);
    } finally {
      setBusy(false);
    }
  }

  return (
    <main className="auth-shell">
      <section className="auth-story">
        <BrandMark />
        <div className="story-content">
          <div className="eyebrow light-eyebrow">
            <span className="eyebrow-dot" /> CONTRACT INTELLIGENCE
          </div>
          <h1>Find the clause.<br />Follow the evidence.</h1>
          <p>
            Ask questions across your agreements and see the passages behind
            every answer.
          </p>
          <div className="story-visual" aria-hidden="true">
            <div className="visual-document">
              <div className="visual-doc-top"><span /> <span /> <span /></div>
              <div className="visual-doc-title" />
              <div className="visual-line wide" />
              <div className="visual-line" />
              <div className="visual-highlight" />
              <div className="visual-line wide" />
              <div className="visual-line short" />
              <div className="visual-line" />
              <div className="visual-line wide" />
            </div>
            <div className="visual-connector"><span /></div>
            <div className="visual-evidence">
              <span className="evidence-kicker">EVIDENCE FOUND</span>
              <strong>Section 8.3</strong>
              <span className="evidence-copy">Liability cap</span>
              <span className="evidence-page">PAGE 5 <i /> VERIFIED</span>
            </div>
            <span className="visual-orbit orbit-one" />
            <span className="visual-orbit orbit-two" />
          </div>
        </div>
        <div className="story-footer"><span>Structure-aware contract Q&amp;A</span><span>01 / PRIVATE WORKSPACE</span></div>
      </section>

      <section className="auth-panel">
        <div className="mobile-brand"><BrandMark /></div>
        <div className="auth-card">
          <div className="auth-heading">
            <div className="eyebrow"><span className="eyebrow-dot" /> YOUR CONTRACT WORKSPACE</div>
            <h2>{mode === "signin" ? "Welcome back" : "Create your account"}</h2>
            <p>{mode === "signin" ? "Sign in to pick up where you left off." : "Set up your account to start exploring contracts."}</p>
          </div>

          {!configured && (
            <div className="form-alert" role="alert">
              Add <code>NEXT_PUBLIC_SUPABASE_URL</code> and <code>NEXT_PUBLIC_SUPABASE_ANON_KEY</code> to <code>web/.env.local</code>, then restart Next.js.
            </div>
          )}
          {error && <div className="form-alert" role="alert">{error}</div>}
          {notice && <div className="form-notice" role="status">{notice}</div>}

          <form className="auth-form" onSubmit={handleSubmit}>
            <label htmlFor="email">Email address</label>
            <input
              id="email"
              type="email"
              autoComplete="email"
              placeholder="you@company.com"
              value={email}
              onChange={(event) => setEmail(event.target.value)}
              required
            />
            <div className="password-label">
              <label htmlFor="password">Password</label>
              {mode === "signin" && <span>At least 6 characters</span>}
            </div>
            <input
              id="password"
              type="password"
              autoComplete={mode === "signin" ? "current-password" : "new-password"}
              placeholder="Enter your password"
              value={password}
              onChange={(event) => setPassword(event.target.value)}
              minLength={6}
              required
            />
            <button className="primary-button auth-submit" type="submit" disabled={busy || !configured}>
              {busy ? "Please wait…" : mode === "signin" ? "Sign in" : "Create account"}
              {!busy && <span aria-hidden="true">↗</span>}
            </button>
          </form>

          <div className="auth-switch">
            {mode === "signin" ? "New to LexGraph?" : "Already have an account?"}{" "}
            <button type="button" onClick={() => { setMode(mode === "signin" ? "signup" : "signin"); setError(""); setNotice(""); }}>
              {mode === "signin" ? "Create an account" : "Sign in"}
            </button>
          </div>
          <div className="auth-footnote"><span className="lock-icon">⌑</span> Your documents stay in your private workspace.</div>
        </div>
        <footer className="auth-legal">LEXGRAPH <span>·</span> CONTRACTS, MADE CLEAR</footer>
      </section>
    </main>
  );
}
