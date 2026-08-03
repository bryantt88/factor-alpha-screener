import './globals.css';

export const metadata = {
  title: 'AI-Power Stack Screener',
  description: 'Idiosyncratic-alpha screener for AI-power-stack equities',
};

export default function RootLayout({ children }) {
  return (
    <html lang="en">
      <body>{children}</body>
    </html>
  );
}
