// ============================================================================
// RICHTUBE - YouTube Intelligence & Autonomous Production Engine
// Copyright (c) Công ty TNHH SNAKEMEDIA. All rights reserved.
// Module: Root Layout (Dark Theme)
// ============================================================================

import type { Metadata } from "next";
import "./globals.css";

export const metadata: Metadata = {
  title: "RICHTUBE OS | SNAKEMEDIA",
  description: "Hệ thống Do thám Thuật toán Đa thị trường & Sản xuất Kịch bản 4 Cột Tự hành",
};

export default function RootLayout({ children }: { children: React.ReactNode }) {
  return (
    <html lang="vi" className="dark">
      <body className="bg-[#090B10] text-slate-100 antialiased">{children}</body>
    </html>
  );
}
