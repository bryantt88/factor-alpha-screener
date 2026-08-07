import './globals.css';

export const metadata = {
  title: 'Factor-Alpha Screener',
  description: 'Factor-model / performance-driver screener — idiosyncratic alpha & market-neutral trade ideas',
};

export default function RootLayout({ children }) {
  return (
    <html lang="en">
      <body>{children}</body>
    </html>
  );
}
