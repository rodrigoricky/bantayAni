import './globals.css';
import RoleBasedLayout from '@/components/layout/RoleBasedLayout';

export const metadata = {
  title: 'Bantay Ani',
  description: 'Satellite Crop Intelligence for Municipal Agricultural Officers',
  icons: { icon: '/logo.png' },
};

export default function RootLayout({ children }) {
  return (
    <html lang="en" className="h-full">
      <body className="h-full overflow-hidden bg-white text-gray-900 antialiased">
        <RoleBasedLayout>{children}</RoleBasedLayout>
      </body>
    </html>
  );
}