'use client';

import React from 'react';
import Link from 'next/link';
import { usePathname } from 'next/navigation';
import { Home, Compass, Image, MessageSquare, User } from 'lucide-react';

export default function BottomNav() {
  const pathname = usePathname();

  const navItems = [
    { name: 'ホーム', href: '/main', icon: <Home className="w-5 h-5" /> },
    { name: 'プラン', href: '/plans', icon: <Compass className="w-5 h-5" /> },
    { name: 'チャット', href: '/chat', icon: <MessageSquare className="w-5 h-5" /> },
    { name: '思い出', href: '/memories', icon: <Image className="w-5 h-5" /> },
    { name: 'マイページ', href: '/me', icon: <User className="w-5 h-5" /> },
  ];

  return (
    <div className="sticky bottom-0 left-0 right-0 bg-[#0f111a]/95 border-t border-white/5 backdrop-blur-md px-4 py-2 z-50 flex justify-around items-center -mx-6">
      {navItems.map((item) => {
        const isActive = pathname.startsWith(item.href);
        return (
          <Link
            key={item.href}
            href={item.href}
            className={`flex flex-col items-center justify-center py-1.5 px-3 rounded-xl transition-all duration-300 ${
              isActive
                ? 'text-indigo-400 font-semibold scale-105 bg-indigo-500/5'
                : 'text-slate-500 hover:text-slate-300'
            }`}
          >
            <div className={`mb-1 transition-transform duration-300 ${isActive ? 'translate-y-[-2px]' : ''}`}>
              {item.icon}
            </div>
            <span className="text-[10px] tracking-wider select-none font-outfit">
              {item.name}
            </span>
          </Link>
        );
      })}
    </div>
  );
}
