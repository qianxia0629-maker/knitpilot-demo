import type { Metadata } from "next";
import "./globals.css";

export const metadata: Metadata = {
  title: "KnitPilot · AI针织工艺师",
  description: "基础圆领针织工艺初稿演示与确定性 QC",
};

export default function RootLayout({ children }: Readonly<{ children: React.ReactNode }>) {
  return <html lang="zh-CN"><body>{children}</body></html>;
}
