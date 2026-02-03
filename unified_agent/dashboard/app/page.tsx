'use client';

import { useEffect } from 'react';
import { useRouter } from 'next/navigation';
import { useAuth } from '@/lib/auth';
import Link from 'next/link';
import { Phone, MessageSquare, Database, Shield, Zap, Users } from 'lucide-react';

export default function HomePage() {
  const router = useRouter();
  const { isAuthenticated, loading } = useAuth();

  useEffect(() => {
    if (!loading && isAuthenticated) {
      router.push('/dashboard');
    }
  }, [loading, isAuthenticated, router]);

  return (
    <div className="min-h-screen bg-gradient-to-br from-blue-900 via-purple-900 to-indigo-900">
      {/* Header */}
      <header className="p-6">
        <nav className="max-w-7xl mx-auto flex justify-between items-center">
          <h1 className="text-2xl font-bold text-white">Unified AI Agent</h1>
          <div className="flex gap-4">
            <Link
              href="/login"
              className="px-4 py-2 text-white hover:text-blue-200 transition"
            >
              Sign In
            </Link>
            <Link
              href="/register"
              className="px-4 py-2 bg-white text-blue-900 rounded-md hover:bg-blue-100 transition"
            >
              Get Started
            </Link>
          </div>
        </nav>
      </header>

      {/* Hero Section */}
      <main className="max-w-7xl mx-auto px-6 py-20">
        <div className="text-center">
          <h2 className="text-5xl font-bold text-white mb-6">
            The Complete AI Agent Platform
          </h2>
          <p className="text-xl text-blue-200 mb-10 max-w-3xl mx-auto">
            Combine voice calling, intelligent chat, and database querying in one unified platform.
            Built for enterprises that demand reliability, security, and scale.
          </p>
          <div className="flex justify-center gap-4">
            <Link
              href="/register"
              className="px-8 py-4 bg-white text-blue-900 rounded-lg font-semibold hover:bg-blue-100 transition flex items-center gap-2"
            >
              <Zap size={20} />
              Start Free Trial
            </Link>
            <Link
              href="/login"
              className="px-8 py-4 border-2 border-white text-white rounded-lg font-semibold hover:bg-white/10 transition"
            >
              View Demo
            </Link>
          </div>
        </div>

        {/* Features Grid */}
        <div className="grid grid-cols-1 md:grid-cols-2 lg:grid-cols-3 gap-8 mt-20">
          <div className="bg-white/10 backdrop-blur-lg rounded-xl p-6">
            <Phone className="text-blue-400 mb-4" size={40} />
            <h3 className="text-xl font-semibold text-white mb-2">Voice Calling</h3>
            <p className="text-blue-200">
              AI-powered outbound and inbound calls via Twilio and Ultravox.
              Natural conversations with real-time transcription.
            </p>
          </div>

          <div className="bg-white/10 backdrop-blur-lg rounded-xl p-6">
            <MessageSquare className="text-purple-400 mb-4" size={40} />
            <h3 className="text-xl font-semibold text-white mb-2">Intelligent Chat</h3>
            <p className="text-blue-200">
              RAG-powered chat with document search. Get accurate answers
              from your knowledge base instantly.
            </p>
          </div>

          <div className="bg-white/10 backdrop-blur-lg rounded-xl p-6">
            <Database className="text-green-400 mb-4" size={40} />
            <h3 className="text-xl font-semibold text-white mb-2">Text-to-SQL</h3>
            <p className="text-blue-200">
              Query your database using natural language. No SQL knowledge
              required - just ask questions.
            </p>
          </div>

          <div className="bg-white/10 backdrop-blur-lg rounded-xl p-6">
            <Shield className="text-yellow-400 mb-4" size={40} />
            <h3 className="text-xl font-semibold text-white mb-2">Enterprise Security</h3>
            <p className="text-blue-200">
              JWT authentication, rate limiting, and webhook security.
              Your data stays protected.
            </p>
          </div>

          <div className="bg-white/10 backdrop-blur-lg rounded-xl p-6">
            <Users className="text-pink-400 mb-4" size={40} />
            <h3 className="text-xl font-semibold text-white mb-2">Multi-Tenant</h3>
            <p className="text-blue-200">
              Full multi-tenant support with isolated data and configurable
              limits per tenant.
            </p>
          </div>

          <div className="bg-white/10 backdrop-blur-lg rounded-xl p-6">
            <Zap className="text-orange-400 mb-4" size={40} />
            <h3 className="text-xl font-semibold text-white mb-2">Lead Capture</h3>
            <p className="text-blue-200">
              Automatically extract and store leads from conversations.
              Never miss a potential customer.
            </p>
          </div>
        </div>

        {/* CTA Section */}
        <div className="mt-20 text-center">
          <h3 className="text-3xl font-bold text-white mb-4">
            Ready to Transform Your Customer Interactions?
          </h3>
          <p className="text-blue-200 mb-8">
            Join hundreds of businesses using Unified AI Agent
          </p>
          <Link
            href="/register"
            className="inline-flex items-center gap-2 px-8 py-4 bg-gradient-to-r from-blue-500 to-purple-500 text-white rounded-lg font-semibold hover:from-blue-600 hover:to-purple-600 transition"
          >
            Get Started Now
          </Link>
        </div>
      </main>

      {/* Footer */}
      <footer className="mt-20 border-t border-white/10 py-8">
        <div className="max-w-7xl mx-auto px-6 text-center text-blue-300">
          <p>&copy; 2024 Unified AI Agent. All rights reserved.</p>
        </div>
      </footer>
    </div>
  );
}
