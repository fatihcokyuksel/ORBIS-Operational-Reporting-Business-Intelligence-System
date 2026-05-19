import Link from "next/link";
import { AlertTriangle, LogIn, UserPlus } from "lucide-react";

const cards = [
  {
    title: "Finansal kararlar için dikkatli kullanın",
    description:
      "ORBIS yardımcı bir asistandır; vergi, muhasebe ve finans kararlarında kritik bilgileri resmi kaynaklarla doğrulayın.",
    icon: AlertTriangle,
    href: null,
  },
  {
    title: "Üye girişi",
    description: "Mevcut hesabınızla devam edin ve sohbet geçmişinize ulaşın.",
    icon: LogIn,
    href: "/signin",
  },
  {
    title: "Kayıt ol",
    description: "Yeni hesap oluşturun ve güçlü bir şifreyle güvenli şekilde başlayın.",
    icon: UserPlus,
    href: "/signup",
  },
] as const;

export default function LoginPage() {
  return (
    <div className="min-h-screen bg-black text-zinc-100 flex flex-col justify-center items-center p-4">
      <div className="w-full max-w-lg space-y-3">
        <div className="text-center mb-6">
          <h1 className="text-3xl font-semibold tracking-tight">ORBIS</h1>
          <p className="text-zinc-500 mt-2 text-sm">Yapay zeka destekli finans ve muhasebe asistanı</p>
        </div>

        {cards.map((card) => {
          const Icon = card.icon;
          const content = (
            <div className="flex items-center gap-4">
              <div className="w-11 h-11 rounded-xl bg-zinc-800 border border-zinc-700 flex items-center justify-center shrink-0 transition-colors duration-200 group-hover:bg-zinc-700">
                <Icon className="w-5 h-5 text-zinc-300" />
              </div>
              <div className="min-w-0">
                <h2 className="font-semibold text-zinc-100">{card.title}</h2>
                <p className="text-sm text-zinc-500 mt-1 leading-6">{card.description}</p>
              </div>
            </div>
          );

          const className =
            "group block w-full rounded-2xl border border-zinc-800 bg-zinc-950 p-5 shadow-xl transition-all duration-300 ease-out hover:-translate-y-0.5 hover:border-zinc-700 hover:bg-zinc-900 hover:shadow-2xl";

          if (!card.href) {
            return (
              <section key={card.title} className={className}>
                {content}
              </section>
            );
          }

          return (
            <Link key={card.title} href={card.href} className={className}>
              {content}
            </Link>
          );
        })}
      </div>
    </div>
  );
}
