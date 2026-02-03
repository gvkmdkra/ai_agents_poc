'use client';

import { useEffect, useState } from 'react';
import { useRouter } from 'next/navigation';
import { useAuth } from '@/lib/auth';
import { callsApi, chatApi, healthApi, Call } from '@/lib/api';
import { Phone, MessageSquare, Activity, LogOut, Send, PhoneCall, PhoneOff, RefreshCw } from 'lucide-react';

export default function DashboardPage() {
  const { user, logout, loading: authLoading, isAuthenticated } = useAuth();
  const router = useRouter();
  const [activeTab, setActiveTab] = useState<'calls' | 'chat'>('calls');
  const [calls, setCalls] = useState<Call[]>([]);
  const [loadingCalls, setLoadingCalls] = useState(false);

  // Call form
  const [phoneNumber, setPhoneNumber] = useState('');
  const [systemPrompt, setSystemPrompt] = useState('');
  const [callingStatus, setCallingStatus] = useState('');

  // Chat form
  const [chatMessage, setChatMessage] = useState('');
  const [chatHistory, setChatHistory] = useState<{role: string, content: string}[]>([]);
  const [chatLoading, setChatLoading] = useState(false);
  const [conversationId, setConversationId] = useState<string | null>(null);

  // Health status
  const [health, setHealth] = useState<any>(null);

  useEffect(() => {
    if (!authLoading && !isAuthenticated) {
      router.push('/login');
    }
  }, [authLoading, isAuthenticated, router]);

  useEffect(() => {
    if (isAuthenticated) {
      fetchCalls();
      fetchHealth();
    }
  }, [isAuthenticated]);

  const fetchCalls = async () => {
    setLoadingCalls(true);
    try {
      const callsList = await callsApi.list(20);
      setCalls(callsList);
    } catch (error) {
      console.error('Failed to fetch calls:', error);
    } finally {
      setLoadingCalls(false);
    }
  };

  const fetchHealth = async () => {
    try {
      const healthData = await healthApi.check();
      setHealth(healthData);
    } catch (error) {
      console.error('Failed to fetch health:', error);
    }
  };

  const handleInitiateCall = async (e: React.FormEvent) => {
    e.preventDefault();
    if (!phoneNumber) return;

    setCallingStatus('Initiating call...');
    try {
      const result = await callsApi.initiate(phoneNumber, systemPrompt || undefined);
      setCallingStatus(`Call initiated! Call ID: ${result.call_id}`);
      setPhoneNumber('');
      setSystemPrompt('');
      setTimeout(fetchCalls, 2000);
    } catch (error: any) {
      setCallingStatus(`Error: ${error.response?.data?.detail || 'Failed to initiate call'}`);
    }
  };

  const handleSendChat = async (e: React.FormEvent) => {
    e.preventDefault();
    if (!chatMessage.trim()) return;

    setChatLoading(true);
    setChatHistory(prev => [...prev, { role: 'user', content: chatMessage }]);

    try {
      const response = await chatApi.send(chatMessage, conversationId || undefined);
      setChatHistory(prev => [...prev, { role: 'assistant', content: response.response || response.message }]);
      if (response.conversation_id) {
        setConversationId(response.conversation_id);
      }
      setChatMessage('');
    } catch (error: any) {
      setChatHistory(prev => [...prev, { role: 'system', content: `Error: ${error.response?.data?.detail || 'Failed to send message'}` }]);
    } finally {
      setChatLoading(false);
    }
  };

  const handleLogout = async () => {
    await logout();
    router.push('/login');
  };

  if (authLoading) {
    return (
      <div className="min-h-screen flex items-center justify-center bg-gray-100">
        <div className="text-xl text-gray-600">Loading...</div>
      </div>
    );
  }

  if (!isAuthenticated) {
    return null;
  }

  return (
    <div className="min-h-screen bg-gray-100">
      {/* Header */}
      <header className="bg-white shadow-sm">
        <div className="max-w-7xl mx-auto px-4 py-4 sm:px-6 lg:px-8 flex justify-between items-center">
          <h1 className="text-2xl font-bold text-gray-900">Unified AI Agent</h1>
          <div className="flex items-center gap-4">
            <span className="text-gray-600">Welcome, {user?.name || user?.email}</span>
            <button
              onClick={handleLogout}
              className="flex items-center gap-2 text-gray-600 hover:text-gray-900"
            >
              <LogOut size={20} />
              Logout
            </button>
          </div>
        </div>
      </header>

      <main className="max-w-7xl mx-auto px-4 py-6 sm:px-6 lg:px-8">
        {/* Health Status */}
        {health && (
          <div className="mb-6 bg-white rounded-lg shadow p-4">
            <div className="flex items-center gap-2">
              <Activity className={health.status === 'healthy' ? 'text-green-500' : 'text-red-500'} size={20} />
              <span className="font-medium">System Status:</span>
              <span className={health.status === 'healthy' ? 'text-green-600' : 'text-red-600'}>
                {health.status === 'healthy' ? 'All Systems Operational' : 'Issues Detected'}
              </span>
            </div>
          </div>
        )}

        {/* Tab Navigation */}
        <div className="mb-6 flex gap-4">
          <button
            onClick={() => setActiveTab('calls')}
            className={`flex items-center gap-2 px-4 py-2 rounded-lg ${
              activeTab === 'calls'
                ? 'bg-blue-600 text-white'
                : 'bg-white text-gray-700 hover:bg-gray-100'
            }`}
          >
            <Phone size={20} />
            Voice Calls
          </button>
          <button
            onClick={() => setActiveTab('chat')}
            className={`flex items-center gap-2 px-4 py-2 rounded-lg ${
              activeTab === 'chat'
                ? 'bg-blue-600 text-white'
                : 'bg-white text-gray-700 hover:bg-gray-100'
            }`}
          >
            <MessageSquare size={20} />
            AI Chat
          </button>
        </div>

        {/* Voice Calls Tab */}
        {activeTab === 'calls' && (
          <div className="grid grid-cols-1 lg:grid-cols-2 gap-6">
            {/* Initiate Call Form */}
            <div className="bg-white rounded-lg shadow p-6">
              <h2 className="text-xl font-semibold mb-4 flex items-center gap-2">
                <PhoneCall size={24} className="text-blue-600" />
                Make a Call
              </h2>
              <form onSubmit={handleInitiateCall} className="space-y-4">
                <div>
                  <label className="block text-sm font-medium text-gray-700 mb-1">
                    Phone Number
                  </label>
                  <input
                    type="tel"
                    value={phoneNumber}
                    onChange={(e) => setPhoneNumber(e.target.value)}
                    placeholder="+1234567890"
                    className="w-full px-3 py-2 border rounded-md focus:outline-none focus:ring-2 focus:ring-blue-500 text-gray-900"
                    required
                  />
                </div>
                <div>
                  <label className="block text-sm font-medium text-gray-700 mb-1">
                    System Prompt (Optional)
                  </label>
                  <textarea
                    value={systemPrompt}
                    onChange={(e) => setSystemPrompt(e.target.value)}
                    placeholder="Custom instructions for the AI agent..."
                    rows={3}
                    className="w-full px-3 py-2 border rounded-md focus:outline-none focus:ring-2 focus:ring-blue-500 text-gray-900"
                  />
                </div>
                <button
                  type="submit"
                  className="w-full bg-blue-600 text-white py-2 rounded-md hover:bg-blue-700 flex items-center justify-center gap-2"
                >
                  <Phone size={20} />
                  Initiate Call
                </button>
              </form>
              {callingStatus && (
                <div className="mt-4 p-3 bg-blue-50 text-blue-700 rounded-md">
                  {callingStatus}
                </div>
              )}
            </div>

            {/* Recent Calls */}
            <div className="bg-white rounded-lg shadow p-6">
              <div className="flex justify-between items-center mb-4">
                <h2 className="text-xl font-semibold flex items-center gap-2">
                  <PhoneOff size={24} className="text-gray-600" />
                  Recent Calls
                </h2>
                <button
                  onClick={fetchCalls}
                  disabled={loadingCalls}
                  className="text-blue-600 hover:text-blue-800"
                >
                  <RefreshCw size={20} className={loadingCalls ? 'animate-spin' : ''} />
                </button>
              </div>
              <div className="space-y-3 max-h-96 overflow-y-auto">
                {calls.length === 0 ? (
                  <p className="text-gray-500 text-center py-4">No calls yet</p>
                ) : (
                  calls.map((call) => (
                    <div
                      key={call.id}
                      className="p-3 border rounded-md hover:bg-gray-50"
                    >
                      <div className="flex justify-between items-start">
                        <div>
                          <p className="font-medium text-gray-900">{call.to_number}</p>
                          <p className="text-sm text-gray-500">
                            {new Date(call.started_at).toLocaleString()}
                          </p>
                        </div>
                        <span
                          className={`px-2 py-1 text-xs rounded-full ${
                            call.status === 'completed'
                              ? 'bg-green-100 text-green-800'
                              : call.status === 'in-progress'
                              ? 'bg-blue-100 text-blue-800'
                              : 'bg-gray-100 text-gray-800'
                          }`}
                        >
                          {call.status}
                        </span>
                      </div>
                      {call.duration_seconds && (
                        <p className="text-sm text-gray-500 mt-1">
                          Duration: {Math.floor(call.duration_seconds / 60)}m {call.duration_seconds % 60}s
                        </p>
                      )}
                    </div>
                  ))
                )}
              </div>
            </div>
          </div>
        )}

        {/* Chat Tab */}
        {activeTab === 'chat' && (
          <div className="bg-white rounded-lg shadow">
            <div className="p-6 border-b">
              <h2 className="text-xl font-semibold flex items-center gap-2">
                <MessageSquare size={24} className="text-blue-600" />
                AI Chat Assistant
              </h2>
              <p className="text-gray-500 text-sm mt-1">
                Ask questions about your data or have a conversation with the AI
              </p>
            </div>

            {/* Chat Messages */}
            <div className="h-96 overflow-y-auto p-6 space-y-4">
              {chatHistory.length === 0 ? (
                <div className="text-center text-gray-500 py-8">
                  Start a conversation by sending a message
                </div>
              ) : (
                chatHistory.map((msg, idx) => (
                  <div
                    key={idx}
                    className={`flex ${msg.role === 'user' ? 'justify-end' : 'justify-start'}`}
                  >
                    <div
                      className={`max-w-[70%] p-3 rounded-lg ${
                        msg.role === 'user'
                          ? 'bg-blue-600 text-white'
                          : msg.role === 'system'
                          ? 'bg-red-100 text-red-700'
                          : 'bg-gray-100 text-gray-900'
                      }`}
                    >
                      {msg.content}
                    </div>
                  </div>
                ))
              )}
              {chatLoading && (
                <div className="flex justify-start">
                  <div className="bg-gray-100 p-3 rounded-lg text-gray-500">
                    Thinking...
                  </div>
                </div>
              )}
            </div>

            {/* Chat Input */}
            <form onSubmit={handleSendChat} className="p-4 border-t">
              <div className="flex gap-2">
                <input
                  type="text"
                  value={chatMessage}
                  onChange={(e) => setChatMessage(e.target.value)}
                  placeholder="Type your message..."
                  className="flex-1 px-4 py-2 border rounded-md focus:outline-none focus:ring-2 focus:ring-blue-500 text-gray-900"
                  disabled={chatLoading}
                />
                <button
                  type="submit"
                  disabled={chatLoading || !chatMessage.trim()}
                  className="bg-blue-600 text-white px-4 py-2 rounded-md hover:bg-blue-700 disabled:opacity-50 flex items-center gap-2"
                >
                  <Send size={20} />
                  Send
                </button>
              </div>
            </form>
          </div>
        )}
      </main>
    </div>
  );
}
