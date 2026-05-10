"use client";

import { useState } from "react";
import { useRouter } from "next/navigation";
import Link from "next/link";
import { Bot, Loader2 } from "lucide-react";

export default function LoginPage() {
  const router = useRouter();
  const [email, setEmail] = useState("");
  const [password, setPassword] = useState("");
  const [error, setError] = useState("");
  const [loading, setLoading] = useState(false);

  const handleSubmit = async (e: React.FormEvent) => {
    e.preventDefault();
    setLoading(true);
    setError("");

    try {
      const res = await fetch("/api/auth/login", {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({ email, password }),
      });

      if (res.ok) {
        router.push("/");
        router.refresh();
      } else {
        const data = await res.json();
        setError(data.message || "Invalid credentials");
      }
    } catch (err) {
      setError("An unexpected error occurred");
    } finally {
      setLoading(false);
    }
  };

  return (
    <div className="min-h-screen bg-black text-zinc-100 flex flex-col justify-center items-center p-4">
      <div className="w-full max-w-md bg-zinc-950 p-8 rounded-2xl border border-zinc-800 shadow-xl">
        <div className="flex flex-col items-center mb-8">
          <div className="w-12 h-12 bg-white rounded-full flex items-center justify-center mb-4">
            <Bot className="w-7 h-7 text-black" />
          </div>
          <h1 className="text-2xl font-semibold">Welcome back</h1>
          <p className="text-zinc-400 mt-2 text-sm">Sign in to continue to your AI Assistant</p>
        </div>

        <form onSubmit={handleSubmit} className="space-y-4">
          {error && (
            <div className="p-3 bg-red-500/10 border border-red-500/20 text-red-400 text-sm rounded-lg text-center">
              {error}
            </div>
          )}

          <div>
            <label className="block text-sm font-medium text-zinc-300 mb-1.5">Email address</label>
            <input
              type="email"
              required
              value={email}
              onChange={(e) => setEmail(e.target.value)}
              className="w-full px-4 py-3 bg-zinc-900 border border-zinc-800 rounded-xl focus:outline-none focus:ring-2 focus:ring-white/20 focus:border-zinc-700 transition-all text-sm"
              placeholder="you@example.com"
            />
          </div>

          <div>
            <label className="block text-sm font-medium text-zinc-300 mb-1.5">Password</label>
            <input
              type="password"
              required
              value={password}
              onChange={(e) => setPassword(e.target.value)}
              className="w-full px-4 py-3 bg-zinc-900 border border-zinc-800 rounded-xl focus:outline-none focus:ring-2 focus:ring-white/20 focus:border-zinc-700 transition-all text-sm"
              placeholder="••••••••"
            />
          </div>

          <button
            type="submit"
            disabled={loading}
            className="w-full bg-white text-black font-medium py-3 rounded-xl hover:bg-zinc-200 transition-colors disabled:opacity-50 disabled:cursor-not-allowed flex items-center justify-center mt-2"
          >
            {loading ? <Loader2 className="w-5 h-5 animate-spin" /> : "Continue"}
          </button>
        </form>

        <div className="mt-6 text-center text-sm text-zinc-500">
          Don't have an account?{" "}
          <Link href="/signup" className="text-white hover:underline transition-all">
            Sign up
          </Link>
        </div>
      </div>
    </div>
  );
}
