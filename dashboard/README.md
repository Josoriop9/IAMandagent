# Hashed Dashboard

Modern, minimalist web dashboard for the Hashed AI Agent Governance Platform.

## 🚀 Quick Start

```bash
# Install dependencies
npm install

# Run development server
npm run dev

# Open browser
# http://localhost:3000
```

## 📁 Project Structure

```
dashboard/
├── app/
│   ├── globals.css          # Global styles with Tailwind
│   ├── layout.tsx           # Root layout
│   ├── page.tsx             # Homepage
│   ├── login/               # Authentication pages (TODO)
│   └── dashboard/           # Protected dashboard pages (TODO)
├── components/              # Reusable React components (TODO)
├── lib/                     # Utilities and configurations (TODO)
├── package.json
├── tsconfig.json
└── tailwind.config.ts
```

## 🎨 Tech Stack

- **Framework**: Next.js 15 (App Router)
- **Language**: TypeScript
- **Styling**: Tailwind CSS
- **Auth**: Supabase Auth
- **Database**: Supabase (shared with backend)
- **Charts**: Recharts
- **Icons**: Lucide React

## 🔐 Authentication

Uses Supabase Auth with support for:
- Email/Password
- Google OAuth (configurable)
- GitHub OAuth (configurable)

## 📊 Features (In Progress)

- [ ] Authentication (Login/Signup)
- [ ] Agent Management Dashboard
- [ ] Policy Configuration UI
- [ ] Real-time Audit Logs Viewer
- [ ] Analytics & Insights
- [ ] Organization Settings

## 🎯 Next Steps

1. Install dependencies: `npm install`
2. Create `.env.local` with Supabase credentials
3. Run dev server: `npm run dev`
4. Build login page
5. Build dashboard pages

## 🔗 Related

- **SDK**: `../src/hashed/` - Python SDK
- **Backend**: `../server/` - FastAPI control plane
- **Database**: `../database/schema.sql` - Supabase schema
