"use client";

import { useState } from "react";
import { useRouter } from "next/navigation";
import Link from "next/link";
import { Bot, Loader2 } from "lucide-react";

const passwordRules = [
  { label: "En az 8 karakter", test: (value: string) => value.length >= 8 },
  { label: "En az bir büyük harf", test: (value: string) => /[A-ZÇĞİÖŞÜ]/.test(value) },
  { label: "En az bir küçük harf", test: (value: string) => /[a-zçğıöşü]/.test(value) },
  { label: "En az bir sayı", test: (value: string) => /\d/.test(value) },
  { label: "En az bir özel karakter (!, ., ?, @, #)", test: (value: string) => /[!.,?@#$%^&*()_\-+=]/.test(value) },
];

function isPasswordValid(value: string) {
  return passwordRules.every((rule) => rule.test(value));
}

export default function SignupPage() {
  const router = useRouter();
  const [name, setName] = useState("");
  const [email, setEmail] = useState("");
  const [password, setPassword] = useState("");
  const [confirmPassword, setConfirmPassword] = useState("");
  const [error, setError] = useState("");
  const [loading, setLoading] = useState(false);

  const handleSubmit = async (e: React.FormEvent) => {
    e.preventDefault();
    if (!isPasswordValid(password)) {
      setError("Şifre büyük harf, küçük harf, sayı ve özel karakter içermelidir");
      return;
    }

    if (password !== confirmPassword) {
      setError("Şifreler eşleşmiyor");
      return;
    }

    setLoading(true);
    setError("");

    try {
      const res = await fetch("/api/auth/register", {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({ name, email, password }),
      });

      if (res.ok) {
        router.push("/");
        router.refresh();
      } else {
        const data = await res.json();
        setError(data.message || "Kayıt tamamlanamadı");
      }
    } catch {
      setError("Beklenmeyen bir hata oluştu");
    } finally {
      setLoading(false);
    }
  };

  return (
    <div className="h-full w-full bg-black text-zinc-100 overflow-y-auto">
      <div className="min-h-full flex flex-col justify-center items-center py-12 px-4">
        <div className="w-full max-w-md bg-zinc-950 p-8 rounded-2xl border border-zinc-800 shadow-xl">
        <div className="flex flex-col items-center mb-8">
          <div className="w-12 h-12 bg-white rounded-full flex items-center justify-center mb-4">
            <Bot className="w-7 h-7 text-black" />
          </div>
          <h1 className="text-2xl font-semibold">Hesabınızı oluşturun</h1>
          <p className="text-zinc-400 mt-2 text-sm">Yapay zeka asistanı platformuna katılın</p>
        </div>

        <form onSubmit={handleSubmit} className="space-y-4">
          {error && (
            <div className="p-3 bg-red-500/10 border border-red-500/20 text-red-400 text-sm rounded-lg text-center">
              {error}
            </div>
          )}

          <div>
            <label className="block text-sm font-medium text-zinc-300 mb-1.5">Ad soyad</label>
            <input
              type="text"
              required
              value={name}
              autoComplete="name"
              onChange={(e) => setName(e.target.value)}
              className="w-full px-4 py-3 bg-zinc-900 border border-zinc-800 rounded-xl focus:outline-none focus:ring-2 focus:ring-white/20 focus:border-zinc-700 transition-all text-sm"
              placeholder="Ad Soyad"
            />
          </div>

          <div>
            <label className="block text-sm font-medium text-zinc-300 mb-1.5">E-posta adresi</label>
            <input
              type="email"
              required
              value={email}
              autoComplete="email"
              onChange={(e) => setEmail(e.target.value)}
              className="w-full px-4 py-3 bg-zinc-900 border border-zinc-800 rounded-xl focus:outline-none focus:ring-2 focus:ring-white/20 focus:border-zinc-700 transition-all text-sm"
              placeholder="ornek@eposta.com"
            />
          </div>

          <div>
            <label className="block text-sm font-medium text-zinc-300 mb-1.5">Şifre</label>
            <input
              type="password"
              required
              value={password}
              autoComplete="new-password"
              onChange={(e) => setPassword(e.target.value)}
              className="w-full px-4 py-3 bg-zinc-900 border border-zinc-800 rounded-xl focus:outline-none focus:ring-2 focus:ring-white/20 focus:border-zinc-700 transition-all text-sm"
              placeholder="••••••••"
            />
          </div>

          <div className="grid grid-cols-1 gap-1.5 rounded-xl border border-zinc-800 bg-zinc-900/60 p-3">
            {passwordRules.map((rule) => {
              const passed = rule.test(password);
              return (
                <p key={rule.label} className={passed ? "text-xs text-emerald-400" : "text-xs text-zinc-500"}>
                  {passed ? "✓" : "•"} {rule.label}
                </p>
              );
            })}
          </div>

          <div>
            <label className="block text-sm font-medium text-zinc-300 mb-1.5">Şifreyi onayla</label>
            <input
              type="password"
              required
              value={confirmPassword}
              autoComplete="new-password"
              onChange={(e) => setConfirmPassword(e.target.value)}
              className="w-full px-4 py-3 bg-zinc-900 border border-zinc-800 rounded-xl focus:outline-none focus:ring-2 focus:ring-white/20 focus:border-zinc-700 transition-all text-sm"
              placeholder="••••••••"
            />
          </div>

          <button
            type="submit"
            disabled={loading}
            className="w-full bg-white text-black font-medium py-3 rounded-xl hover:bg-zinc-200 transition-colors disabled:opacity-50 disabled:cursor-not-allowed flex items-center justify-center mt-2"
          >
            {loading ? <Loader2 className="w-5 h-5 animate-spin" /> : "Kayıt ol"}
          </button>
        </form>

        <div className="mt-6 border-t border-zinc-800/60 pt-6 text-center text-sm text-zinc-400">
          Zaten hesabınız var mı?{" "}
          <Link href="/signin" className="font-semibold text-zinc-100 hover:text-white hover:underline decoration-zinc-500 underline-offset-4 transition-all">
            Giriş yap
          </Link>
        </div>
        </div>
      </div>
    </div>
  );
}
