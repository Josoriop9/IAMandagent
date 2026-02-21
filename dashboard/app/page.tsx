import Link from "next/link";

export default function Home() {
  return (
    <div className="min-h-screen bg-dark overflow-hidden">
      {/* Background Effects */}
      <div className="absolute inset-0 overflow-hidden pointer-events-none">
        <div className="absolute top-0 left-1/4 w-96 h-96 bg-primary-500/20 rounded-full blur-[128px]" />
        <div className="absolute top-1/4 right-1/4 w-96 h-96 bg-purple-500/20 rounded-full blur-[128px]" />
        <div className="absolute bottom-0 left-1/2 w-96 h-96 bg-blue-500/10 rounded-full blur-[128px]" />
      </div>

      {/* Navigation */}
      <nav className="relative z-10 max-w-7xl mx-auto px-6 py-6 flex justify-between items-center">
        <div className="flex items-center gap-2">
          <div className="w-8 h-8 bg-gradient-to-br from-primary-500 to-purple-500 rounded-lg" />
          <span className="text-xl font-bold">Hashed</span>
        </div>
        <div className="flex items-center gap-4">
          <Link href="/login" className="text-gray-400 hover:text-white transition-colors">
            Login
          </Link>
          <Link
            href="/login"
            className="px-4 py-2 bg-white text-black rounded-lg font-medium hover:bg-gray-100 transition-all"
          >
            Get Started
          </Link>
        </div>
      </nav>

      {/* Hero Section */}
      <section className="relative z-10 max-w-7xl mx-auto px-6 pt-20 pb-32">
        <div className="text-center space-y-8 max-w-4xl mx-auto">
          {/* Badge */}
          <div className="inline-flex items-center gap-2 px-4 py-2 bg-dark-light/50 backdrop-blur-sm border border-dark-lighter rounded-full">
            <span className="relative flex h-2 w-2">
              <span className="animate-ping absolute inline-flex h-full w-full rounded-full bg-primary-400 opacity-75"></span>
              <span className="relative inline-flex rounded-full h-2 w-2 bg-primary-500"></span>
            </span>
            <span className="text-sm text-gray-300">Production-ready AI governance</span>
          </div>

          {/* Main Headline */}
          <h1 className="text-6xl md:text-7xl lg:text-8xl font-bold tracking-tight">
            <span className="block mb-2">Stop Rogue</span>
            <span className="block bg-gradient-to-r from-primary-400 via-purple-400 to-pink-400 bg-clip-text text-transparent">
              AI Agents
            </span>
          </h1>

          {/* Subheadline */}
          <p className="text-xl md:text-2xl text-gray-400 max-w-2xl mx-auto leading-relaxed">
            The governance layer your AI agents need. Policies, audit trails, and cryptographic identity - all in one platform.
          </p>

          {/* CTA Buttons */}
          <div className="flex flex-col sm:flex-row gap-4 justify-center pt-8">
            <Link
              href="/login"
              className="group px-8 py-4 bg-gradient-to-r from-primary-500 to-purple-500 rounded-xl font-semibold text-lg hover:shadow-2xl hover:shadow-primary-500/50 transition-all transform hover:scale-105"
            >
              <span className="flex items-center justify-center gap-2">
                Start Free
                <svg className="w-5 h-5 group-hover:translate-x-1 transition-transform" fill="none" viewBox="0 0 24 24" stroke="currentColor">
                  <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M17 8l4 4m0 0l-4 4m4-4H3" />
                </svg>
              </span>
            </Link>
            <Link
              href="#demo"
              className="px-8 py-4 bg-dark-light/50 backdrop-blur-sm border border-dark-lighter rounded-xl font-semibold text-lg hover:bg-dark-light transition-all"
            >
              Watch Demo
            </Link>
          </div>

          {/* Social Proof */}
          <div className="pt-8 flex flex-col sm:flex-row items-center justify-center gap-8 text-sm text-gray-500">
            <div className="flex items-center gap-2">
              <svg className="w-5 h-5 text-green-400" fill="currentColor" viewBox="0 0 20 20">
                <path fillRule="evenodd" d="M10 18a8 8 0 100-16 8 8 0 000 16zm3.707-9.293a1 1 0 00-1.414-1.414L9 10.586 7.707 9.293a1 1 0 00-1.414 1.414l2 2a1 1 0 001.414 0l4-4z" clipRule="evenodd" />
              </svg>
              <span>No credit card required</span>
            </div>
            <div className="flex items-center gap-2">
              <svg className="w-5 h-5 text-green-400" fill="currentColor" viewBox="0 0 20 20">
                <path fillRule="evenodd" d="M10 18a8 8 0 100-16 8 8 0 000 16zm3.707-9.293a1 1 0 00-1.414-1.414L9 10.586 7.707 9.293a1 1 0 00-1.414 1.414l2 2a1 1 0 001.414 0l4-4z" clipRule="evenodd" />
              </svg>
              <span>5-minute setup</span>
            </div>
            <div className="flex items-center gap-2">
              <svg className="w-5 h-5 text-green-400" fill="currentColor" viewBox="0 0 20 20">
                <path fillRule="evenodd" d="M10 18a8 8 0 100-16 8 8 0 000 16zm3.707-9.293a1 1 0 00-1.414-1.414L9 10.586 7.707 9.293a1 1 0 00-1.414 1.414l2 2a1 1 0 001.414 0l4-4z" clipRule="evenodd" />
              </svg>
              <span>SOC 2 ready</span>
            </div>
          </div>
        </div>
      </section>

      {/* Stats Section */}
      <section className="relative z-10 max-w-7xl mx-auto px-6 pb-20">
        <div className="grid grid-cols-2 md:grid-cols-4 gap-8">
          <div className="text-center">
            <div className="text-4xl md:text-5xl font-bold bg-gradient-to-r from-primary-400 to-purple-400 bg-clip-text text-transparent">
              99.9%
            </div>
            <div className="text-gray-400 mt-2">Uptime SLA</div>
          </div>
          <div className="text-center">
            <div className="text-4xl md:text-5xl font-bold bg-gradient-to-r from-purple-400 to-pink-400 bg-clip-text text-transparent">
              &lt;50ms
            </div>
            <div className="text-gray-400 mt-2">Policy Check</div>
          </div>
          <div className="text-center">
            <div className="text-4xl md:text-5xl font-bold bg-gradient-to-r from-pink-400 to-primary-400 bg-clip-text text-transparent">
              100%
            </div>
            <div className="text-gray-400 mt-2">Audit Trail</div>
          </div>
          <div className="text-center">
            <div className="text-4xl md:text-5xl font-bold bg-gradient-to-r from-blue-400 to-primary-400 bg-clip-text text-transparent">
              SOC 2
            </div>
            <div className="text-gray-400 mt-2">Compliant</div>
          </div>
        </div>
      </section>

      {/* Features Section */}
      <section className="relative z-10 max-w-7xl mx-auto px-6 py-32">
        <div className="text-center mb-20">
          <h2 className="text-4xl md:text-5xl font-bold mb-4">
            Everything you need to
            <span className="block mt-2 bg-gradient-to-r from-primary-400 to-purple-400 bg-clip-text text-transparent">
              govern AI agents
            </span>
          </h2>
          <p className="text-xl text-gray-400 max-w-2xl mx-auto">
            Built for production. Designed for developers. Trusted by teams.
          </p>
        </div>

        <div className="grid md:grid-cols-3 gap-6">
          {/* Feature 1 */}
          <div className="group relative bg-gradient-to-b from-dark-light/50 to-dark-light/30 backdrop-blur-sm border border-dark-lighter rounded-2xl p-8 hover:border-primary-500/50 transition-all">
            <div className="absolute inset-0 bg-gradient-to-b from-primary-500/5 to-transparent opacity-0 group-hover:opacity-100 transition-opacity rounded-2xl" />
            <div className="relative">
              <div className="w-12 h-12 bg-gradient-to-br from-primary-500 to-purple-500 rounded-xl flex items-center justify-center text-2xl mb-4">
                🤖
              </div>
              <h3 className="text-2xl font-semibold mb-3">Agent Identity</h3>
              <p className="text-gray-400 leading-relaxed">
                Cryptographic Ed25519 signatures for every agent. Know exactly who did what, when, and why.
              </p>
              <div className="mt-6 pt-6 border-t border-dark-lighter">
                <ul className="space-y-2 text-sm text-gray-400">
                  <li className="flex items-center gap-2">
                    <svg className="w-4 h-4 text-primary-400" fill="currentColor" viewBox="0 0 20 20">
                      <path fillRule="evenodd" d="M16.707 5.293a1 1 0 010 1.414l-8 8a1 1 0 01-1.414 0l-4-4a1 1 0 011.414-1.414L8 12.586l7.293-7.293a1 1 0 011.414 0z" clipRule="evenodd" />
                    </svg>
                    Non-repudiation
                  </li>
                  <li className="flex items-center gap-2">
                    <svg className="w-4 h-4 text-primary-400" fill="currentColor" viewBox="0 0 20 20">
                      <path fillRule="evenodd" d="M16.707 5.293a1 1 0 010 1.414l-8 8a1 1 0 01-1.414 0l-4-4a1 1 0 011.414-1.414L8 12.586l7.293-7.293a1 1 0 011.414 0z" clipRule="evenodd" />
                    </svg>
                    Zero trust architecture
                  </li>
                </ul>
              </div>
            </div>
          </div>

          {/* Feature 2 */}
          <div className="group relative bg-gradient-to-b from-dark-light/50 to-dark-light/30 backdrop-blur-sm border border-dark-lighter rounded-2xl p-8 hover:border-purple-500/50 transition-all">
            <div className="absolute inset-0 bg-gradient-to-b from-purple-500/5 to-transparent opacity-0 group-hover:opacity-100 transition-opacity rounded-2xl" />
            <div className="relative">
              <div className="w-12 h-12 bg-gradient-to-br from-purple-500 to-pink-500 rounded-xl flex items-center justify-center text-2xl mb-4">
                🛡️
              </div>
              <h3 className="text-2xl font-semibold mb-3">Policy Engine</h3>
              <p className="text-gray-400 leading-relaxed">
                Define what agents can and can't do. Enforce limits, approvals, and time windows with ease.
              </p>
              <div className="mt-6 pt-6 border-t border-dark-lighter">
                <ul className="space-y-2 text-sm text-gray-400">
                  <li className="flex items-center gap-2">
                    <svg className="w-4 h-4 text-purple-400" fill="currentColor" viewBox="0 0 20 20">
                      <path fillRule="evenodd" d="M16.707 5.293a1 1 0 010 1.414l-8 8a1 1 0 01-1.414 0l-4-4a1 1 0 011.414-1.414L8 12.586l7.293-7.293a1 1 0 011.414 0z" clipRule="evenodd" />
                    </svg>
                    Amount limits
                  </li>
                  <li className="flex items-center gap-2">
                    <svg className="w-4 h-4 text-purple-400" fill="currentColor" viewBox="0 0 20 20">
                      <path fillRule="evenodd" d="M16.707 5.293a1 1 0 010 1.414l-8 8a1 1 0 01-1.414 0l-4-4a1 1 0 011.414-1.414L8 12.586l7.293-7.293a1 1 0 011.414 0z" clipRule="evenodd" />
                    </svg>
                    Human-in-the-loop
                  </li>
                </ul>
              </div>
            </div>
          </div>

          {/* Feature 3 */}
          <div className="group relative bg-gradient-to-b from-dark-light/50 to-dark-light/30 backdrop-blur-sm border border-dark-lighter rounded-2xl p-8 hover:border-pink-500/50 transition-all">
            <div className="absolute inset-0 bg-gradient-to-b from-pink-500/5 to-transparent opacity-0 group-hover:opacity-100 transition-opacity rounded-2xl" />
            <div className="relative">
              <div className="w-12 h-12 bg-gradient-to-br from-pink-500 to-primary-500 rounded-xl flex items-center justify-center text-2xl mb-4">
                📊
              </div>
              <h3 className="text-2xl font-semibold mb-3">Immutable Logs</h3>
              <p className="text-gray-400 leading-relaxed">
                Every action is logged with cryptographic proof. Perfect for compliance and debugging.
              </p>
              <div className="mt-6 pt-6 border-t border-dark-lighter">
                <ul className="space-y-2 text-sm text-gray-400">
                  <li className="flex items-center gap-2">
                    <svg className="w-4 h-4 text-pink-400" fill="currentColor" viewBox="0 0 20 20">
                      <path fillRule="evenodd" d="M16.707 5.293a1 1 0 010 1.414l-8 8a1 1 0 01-1.414 0l-4-4a1 1 0 011.414-1.414L8 12.586l7.293-7.293a1 1 0 011.414 0z" clipRule="evenodd" />
                    </svg>
                    Tamper-proof
                  </li>
                  <li className="flex items-center gap-2">
                    <svg className="w-4 h-4 text-pink-400" fill="currentColor" viewBox="0 0 20 20">
                      <path fillRule="evenodd" d="M16.707 5.293a1 1 0 010 1.414l-8 8a1 1 0 01-1.414 0l-4-4a1 1 0 011.414-1.414L8 12.586l7.293-7.293a1 1 0 011.414 0z" clipRule="evenodd" />
                    </svg>
                    Real-time sync
                  </li>
                </ul>
              </div>
            </div>
          </div>
        </div>
      </section>

      {/* Code Example Section */}
      <section className="relative z-10 max-w-7xl mx-auto px-6 py-32">
        <div className="grid md:grid-cols-2 gap-12 items-center">
          <div>
            <div className="inline-block px-4 py-2 bg-primary-500/10 border border-primary-500/20 rounded-full text-primary-400 text-sm font-medium mb-6">
              Developer First
            </div>
            <h2 className="text-4xl md:text-5xl font-bold mb-6">
              Integrate in
              <span className="block mt-2 bg-gradient-to-r from-primary-400 to-purple-400 bg-clip-text text-transparent">
                5 minutes
              </span>
            </h2>
            <p className="text-xl text-gray-400 mb-8">
              One decorator is all it takes. Secure your AI agents without changing your codebase.
            </p>
            <Link
              href="/login"
              className="inline-flex items-center gap-2 px-6 py-3 bg-dark-light border border-dark-lighter rounded-lg hover:border-primary-500/50 transition-all group"
            >
              <span>Read Documentation</span>
              <svg className="w-5 h-5 group-hover:translate-x-1 transition-transform" fill="none" viewBox="0 0 24 24" stroke="currentColor">
                <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M17 8l4 4m0 0l-4 4m4-4H3" />
              </svg>
            </Link>
          </div>

          <div className="relative">
            <div className="absolute inset-0 bg-gradient-to-r from-primary-500/20 to-purple-500/20 blur-3xl" />
            <div className="relative bg-dark-light/50 backdrop-blur-sm border border-dark-lighter rounded-2xl p-6 font-mono text-sm">
              <div className="flex items-center gap-2 mb-4 pb-4 border-b border-dark-lighter">
                <div className="w-3 h-3 rounded-full bg-red-500" />
                <div className="w-3 h-3 rounded-full bg-yellow-500" />
                <div className="w-3 h-3 rounded-full bg-green-500" />
                <span className="ml-2 text-gray-400">agent.py</span>
              </div>
              <pre className="text-gray-300 overflow-x-auto">
{`from hashed import HashedCore

core = HashedCore(
  api_key="your_key",
  policies={
    "transfer_money": {
      "max_amount": 1000,
      "allowed": True
    }
  }
)

@core.guard("transfer_money")
async def transfer(amount, to):
    # Your code here
    ...`}
              </pre>
            </div>
          </div>
        </div>
      </section>

      {/* Final CTA */}
      <section className="relative z-10 max-w-7xl mx-auto px-6 py-32">
        <div className="relative bg-gradient-to-r from-primary-500/10 via-purple-500/10 to-pink-500/10 border border-primary-500/20 rounded-3xl p-12 md:p-20 text-center overflow-hidden">
          <div className="absolute inset-0 bg-[url('/grid.svg')] opacity-10" />
          <div className="relative">
            <h2 className="text-4xl md:text-6xl font-bold mb-6">
              Ready to secure your
              <span className="block mt-2 bg-gradient-to-r from-primary-400 to-purple-400 bg-clip-text text-transparent">
                AI agents?
              </span>
            </h2>
            <p className="text-xl text-gray-400 mb-12 max-w-2xl mx-auto">
              Join teams building the next generation of AI. Start free, no credit card required.
            </p>
            <div className="flex flex-col sm:flex-row gap-4 justify-center">
              <Link
                href="/login"
                className="px-8 py-4 bg-white text-black rounded-xl font-semibold text-lg hover:shadow-2xl hover:shadow-white/20 transition-all transform hover:scale-105"
              >
                Get Started Free
              </Link>
              <Link
                href="mailto:hello@hashed.dev"
                className="px-8 py-4 bg-dark-light/50 backdrop-blur-sm border border-dark-lighter rounded-xl font-semibold text-lg hover:bg-dark-light transition-all"
              >
                Contact Sales
              </Link>
            </div>
          </div>
        </div>
      </section>

      {/* Footer */}
      <footer className="relative z-10 max-w-7xl mx-auto px-6 py-12 border-t border-dark-lighter">
        <div className="flex flex-col md:flex-row justify-between items-center gap-4">
          <div className="flex items-center gap-2">
            <div className="w-6 h-6 bg-gradient-to-br from-primary-500 to-purple-500 rounded" />
            <span className="font-semibold">Hashed</span>
          </div>
          <div className="text-sm text-gray-500">
            © 2026 Hashed. All rights reserved.
          </div>
          <div className="flex gap-6 text-sm text-gray-400">
            <Link href="/docs" className="hover:text-white transition-colors">Docs</Link>
            <Link href="/pricing" className="hover:text-white transition-colors">Pricing</Link>
            <Link href="/blog" className="hover:text-white transition-colors">Blog</Link>
          </div>
        </div>
      </footer>
    </div>
  );
}
