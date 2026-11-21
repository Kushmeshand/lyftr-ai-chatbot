import React, { useState, useEffect, useRef } from 'react';
import { 
  Send, 
  RotateCcw, 
  Zap, 
  Database, 
  Clock, 
  Key, 
  AlertCircle, 
  CheckCircle2, 
  Sparkles, 
  Sliders, 
  Terminal,
  Activity,
  Layers,
  ShieldCheck,
  ShieldAlert
} from 'lucide-react';

const API_BASE = import.meta.env.VITE_BACKEND_URL || import.meta.env.VITE_API_URL || 'http://localhost:8000';

// Generate clean unique session id on each page load: 1-128 chars
const generateSessionId = () => `s-${Math.random().toString(36).substring(2, 10)}`;

export default function App() {
  const [sessionId, setSessionId] = useState(generateSessionId);
  const [messages, setMessages] = useState([]);
  const [inputMessage, setInputMessage] = useState('');
  const [systemPrompt, setSystemPrompt] = useState('You are a helpful and concise AI assistant.');
  const [isLoading, setIsLoading] = useState(false);
  const [healthStatus, setHealthStatus] = useState(null);
  const [simulateFailure, setSimulateFailure] = useState('');
  const [showSettings, setShowSettings] = useState(false);
  const [errorBanner, setErrorBanner] = useState(null);

  const messagesEndRef = useRef(null);
  const inputRef = useRef(null);

  const scrollToBottom = () => {
    messagesEndRef.current?.scrollIntoView({ behavior: 'smooth' });
  };

  useEffect(() => {
    scrollToBottom();
  }, [messages, isLoading]);

  // Check health on mount
  useEffect(() => {
    const checkHealth = async () => {
      try {
        const res = await fetch(`${API_BASE}/health`);
        if (res.ok) {
          const data = await res.json();
          setHealthStatus(data);
        } else {
          setHealthStatus({ status: 'unhealthy' });
        }
      } catch (err) {
        setHealthStatus({ status: 'offline', error: err.message });
      }
    };
    checkHealth();
    const interval = setInterval(checkHealth, 30000);
    return () => clearInterval(interval);
  }, []);

  const handleNewSession = () => {
    setSessionId(generateSessionId());
    setMessages([]);
    setErrorBanner(null);
  };

  const handleSend = async (e) => {
    e?.preventDefault();
    const trimmed = inputMessage.trim();
    if (!trimmed || isLoading) return;

    // Immediately clear input as required by contract
    setInputMessage('');
    setErrorBanner(null);

    const userMsg = {
      id: Date.now(),
      role: 'user',
      content: trimmed,
      timestamp: new Date().toLocaleTimeString([], { hour: '2-digit', minute: '2-digit' }),
    };

    setMessages((prev) => [...prev, userMsg]);
    setIsLoading(true);

    try {
      const headers = {
        'Content-Type': 'application/json',
      };
      if (simulateFailure) {
        headers['X-Simulate-Failure'] = simulateFailure;
      }

      const payload = {
        session_id: sessionId,
        message: trimmed,
      };
      if (systemPrompt.trim()) {
        payload.system_prompt = systemPrompt.trim();
      }

      const res = await fetch(`${API_BASE}/chat`, {
        method: 'POST',
        headers,
        body: JSON.stringify(payload),
      });

      const data = await res.json();

      if (!res.ok) {
        // Detailed error returned by backend (e.g. 422 or 503)
        const errorMessage = data?.detail 
          ? (typeof data.detail === 'object' ? JSON.stringify(data.detail) : data.detail)
          : `Error ${res.status}: ${res.statusText}`;
        
        // Add readable error in chat
        setMessages((prev) => [
          ...prev,
          {
            id: Date.now() + 1,
            role: 'error',
            status: res.status,
            content: errorMessage,
            timestamp: new Date().toLocaleTimeString([], { hour: '2-digit', minute: '2-digit' }),
          },
        ]);
        setErrorBanner(`Request failed with status ${res.status}: ${errorMessage}`);
      } else {
        // Success
        const assistantMsg = {
          id: Date.now() + 1,
          role: 'assistant',
          content: data.reply,
          metadata: data.metadata,
          timestamp: new Date().toLocaleTimeString([], { hour: '2-digit', minute: '2-digit' }),
        };
        setMessages((prev) => [...prev, assistantMsg]);
      }
    } catch (err) {
      setMessages((prev) => [
        ...prev,
        {
          id: Date.now() + 1,
          role: 'error',
          status: 0,
          content: `Network or Connection Error: ${err.message}. Please verify the backend is running.`,
          timestamp: new Date().toLocaleTimeString([], { hour: '2-digit', minute: '2-digit' }),
        },
      ]);
      setErrorBanner(`Connection error: ${err.message}`);
    } finally {
      setIsLoading(false);
      setTimeout(() => inputRef.current?.focus(), 50);
    }
  };

  const handleKeyDown = (e) => {
    if (e.key === 'Enter' && !e.shiftKey) {
      e.preventDefault();
      handleSend();
    }
  };

  return (
    <div className="flex flex-col h-screen max-h-screen bg-slate-950 text-slate-100">
      {/* Top Navigation Bar */}
      <header className="border-b border-slate-800 bg-slate-900/70 backdrop-blur-md px-4 py-3 flex items-center justify-between z-10">
        <div className="flex items-center space-x-3">
          <div className="w-9 h-9 rounded-xl bg-gradient-to-tr from-emerald-500 to-teal-400 flex items-center justify-center shadow-lg shadow-emerald-500/20">
            <Sparkles className="w-5 h-5 text-slate-950" />
          </div>
          <div>
            <h1 className="text-base font-bold tracking-tight text-white flex items-center gap-2">
              Lyftr AI Gateway
              <span className="text-xs font-medium px-2 py-0.5 rounded-full bg-emerald-500/10 text-emerald-400 border border-emerald-500/20">
                Failover & Caching
              </span>
            </h1>
            <div className="flex items-center gap-3 text-xs text-slate-400">
              <span className="font-mono text-slate-300">Session: {sessionId}</span>
            </div>
          </div>
        </div>

        <div className="flex items-center space-x-3">
          {/* Health Indicator */}
          <div className="hidden sm:flex items-center gap-1.5 px-2.5 py-1 rounded-full text-xs font-medium bg-slate-800/80 border border-slate-700/60">
            <span className={`w-2 h-2 rounded-full ${
              healthStatus?.status === 'ok' ? 'bg-emerald-400 animate-pulse' : 'bg-amber-400'
            }`} />
            <span className="text-slate-300">
              {healthStatus?.status === 'ok' 
                ? `Keys: ${healthStatus.keys_configured} | Cache: Active` 
                : (healthStatus?.status || 'Connecting...')}
            </span>
          </div>

          <button
            onClick={() => setShowSettings(!showSettings)}
            className={`p-2 rounded-lg border transition-colors ${
              showSettings 
                ? 'bg-emerald-500/10 text-emerald-400 border-emerald-500/30' 
                : 'bg-slate-800/70 hover:bg-slate-800 text-slate-300 border-slate-700'
            }`}
            title="Toggle Settings & Failure Simulation"
          >
            <Sliders className="w-4 h-4" />
          </button>

          <button
            onClick={handleNewSession}
            className="flex items-center gap-1.5 px-3 py-1.5 rounded-lg bg-slate-800 hover:bg-slate-700 text-slate-200 border border-slate-700 text-xs font-medium transition-colors"
            title="Start New Session (Clean Context)"
          >
            <RotateCcw className="w-3.5 h-3.5" />
            <span>New Chat</span>
          </button>
        </div>
      </header>

      {/* Settings / Simulation Drawer */}
      {showSettings && (
        <div className="border-b border-slate-800 bg-slate-900/90 px-4 py-3 text-xs space-y-3">
          <div className="max-w-4xl mx-auto grid grid-cols-1 md:grid-cols-2 gap-4">
            <div>
              <label className="block font-medium text-slate-300 mb-1 flex items-center gap-1.5">
                <Sliders className="w-3.5 h-3.5 text-emerald-400" />
                System Prompt (Optional Session Override)
              </label>
              <input
                data-testid="system-prompt-input"
                type="text"
                value={systemPrompt}
                onChange={(e) => setSystemPrompt(e.target.value)}
                placeholder="Enter custom system prompt..."
                className="w-full bg-slate-950 border border-slate-700 rounded px-2.5 py-1.5 text-slate-200 focus:outline-none focus:border-emerald-500 transition-colors"
              />
            </div>

            <div>
              <label className="block font-medium text-slate-300 mb-1 flex items-center gap-1.5">
                <ShieldAlert className="w-3.5 h-3.5 text-amber-400" />
                Failover Simulation Hook (<code className="text-emerald-400">X-Simulate-Failure</code>)
              </label>
              <div className="flex gap-2">
                <select
                  value={simulateFailure}
                  onChange={(e) => setSimulateFailure(e.target.value)}
                  className="bg-slate-950 border border-slate-700 rounded px-2.5 py-1.5 text-slate-200 focus:outline-none focus:border-emerald-500 transition-colors flex-1"
                >
                  <option value="">None (Normal real traffic)</option>
                  <option value="key_1=429">key_1=429 (Fail key 1 with 429 Rate Limit)</option>
                  <option value="key_1=500">key_1=500 (Fail key 1 with 500 Server Error)</option>
                  <option value="key_1=429,key_2=500">key_1=429,key_2=500 (Fail key 1 &amp; key 2)</option>
                  <option value="*=429">*=429 (Fail all keys -&gt; 503 error)</option>
                </select>
                {simulateFailure && (
                  <button 
                    onClick={() => setSimulateFailure('')}
                    className="px-2 py-1 text-slate-400 hover:text-slate-200 underline"
                  >
                    Clear
                  </button>
                )}
              </div>
            </div>
          </div>
        </div>
      )}

      {/* Global Error Banner if any */}
      {errorBanner && (
        <div className="bg-red-500/10 border-b border-red-500/20 px-4 py-2 flex items-center justify-between text-xs text-red-400">
          <div className="flex items-center gap-2">
            <AlertCircle className="w-4 h-4 flex-shrink-0" />
            <span>{errorBanner}</span>
          </div>
          <button onClick={() => setErrorBanner(null)} className="hover:text-red-200 font-semibold">✕</button>
        </div>
      )}

      {/* Chat Messages Container */}
      <main className="flex-1 overflow-y-auto p-4 sm:p-6 space-y-4 max-w-4xl w-full mx-auto">
        {messages.length === 0 ? (
          <div className="h-full flex flex-col items-center justify-center text-center p-6 text-slate-500 space-y-4">
            <div className="w-16 h-16 rounded-2xl bg-slate-900 border border-slate-800 flex items-center justify-center text-emerald-400 shadow-inner">
              <Zap className="w-8 h-8" />
            </div>
            <div className="space-y-1">
              <h2 className="text-lg font-semibold text-slate-200">Resilient Gemini Chat Gateway</h2>
              <p className="text-xs text-slate-400 max-w-md">
                Automatic multi-key failover on 429, quota, and 5xx errors. Instant LiteLLM response caching for identical context queries.
              </p>
            </div>
            <div className="flex flex-wrap justify-center gap-2 max-w-md pt-2">
              <button 
                onClick={() => setInputMessage("What is the capital of France?")}
                className="px-3 py-1.5 rounded-lg bg-slate-900 hover:bg-slate-800 border border-slate-800 text-xs text-slate-300 transition-colors"
              >
                "What is the capital of France?"
              </button>
              <button 
                onClick={() => setInputMessage("Explain quantum computing in one sentence.")}
                className="px-3 py-1.5 rounded-lg bg-slate-900 hover:bg-slate-800 border border-slate-800 text-xs text-slate-300 transition-colors"
              >
                "Explain quantum computing in one sentence."
              </button>
            </div>
          </div>
        ) : (
          messages.map((msg) => {
            if (msg.role === 'user') {
              return (
                <div key={msg.id} className="flex flex-col items-end">
                  <div className="max-w-[85%] sm:max-w-[75%] rounded-2xl rounded-tr-sm bg-emerald-600 px-4 py-2.5 text-white shadow-md text-sm">
                    <p className="whitespace-pre-wrap">{msg.content}</p>
                  </div>
                  <span className="text-[10px] text-slate-500 mt-1 mr-1">{msg.timestamp}</span>
                </div>
              );
            }

            if (msg.role === 'error') {
              return (
                <div key={msg.id} className="flex flex-col items-start">
                  <div className="max-w-[90%] sm:max-w-[80%] rounded-2xl rounded-tl-sm bg-red-950/40 border border-red-500/30 px-4 py-3 text-red-200 text-sm shadow-md">
                    <div className="flex items-center gap-2 font-semibold text-red-400 text-xs mb-1">
                      <AlertCircle className="w-4 h-4 text-red-400" />
                      <span>Request Failed ({msg.status ? `Status ${msg.status}` : 'Client Error'})</span>
                    </div>
                    <p className="whitespace-pre-wrap text-xs text-red-300">{msg.content}</p>
                  </div>
                  <span className="text-[10px] text-slate-500 mt-1 ml-1">{msg.timestamp}</span>
                </div>
              );
            }

            // Assistant message - EXACT CONTRACT REQUIREMENTS
            const meta = msg.metadata || {};
            const isCache = meta.resolution_source === 'LLM_CACHE';

            return (
              <div 
                key={msg.id} 
                data-testid="assistant-message"
                className="flex flex-col items-start w-full group"
              >
                <div className="max-w-[95%] sm:max-w-[85%] rounded-2xl rounded-tl-sm bg-slate-900 border border-slate-800/80 px-4 py-3 text-slate-100 shadow-md">
                  {/* Reply text */}
                  <div className="text-sm leading-relaxed whitespace-pre-wrap prose prose-invert max-w-none">
                    {msg.content}
                  </div>

                  {/* Metadata Element Section */}
                  <div className="mt-3 pt-2.5 border-t border-slate-800/60 flex flex-wrap items-center gap-2 text-xs">
                    {/* Resolution Source */}
                    <span 
                      data-testid="meta-source"
                      className={`inline-flex items-center gap-1 px-2 py-0.5 rounded font-mono font-semibold text-[11px] ${
                        isCache 
                          ? 'bg-purple-500/20 text-purple-300 border border-purple-500/30' 
                          : 'bg-emerald-500/20 text-emerald-300 border border-emerald-500/30'
                      }`}
                    >
                      {isCache ? <Database className="w-3 h-3" /> : <Zap className="w-3 h-3" />}
                      {meta.resolution_source}
                    </span>

                    {/* Model */}
                    <span 
                      data-testid="meta-model"
                      className="inline-flex items-center gap-1 px-2 py-0.5 rounded bg-slate-800 text-slate-300 font-mono text-[11px] border border-slate-700/50"
                    >
                      <Layers className="w-3 h-3 text-slate-400" />
                      {meta.model}
                    </span>

                    {/* Latency */}
                    <span 
                      data-testid="meta-latency"
                      className="inline-flex items-center gap-1 px-2 py-0.5 rounded bg-slate-800 text-slate-300 font-mono text-[11px] border border-slate-700/50"
                    >
                      <Clock className="w-3 h-3 text-amber-400" />
                      {meta.latency_ms} ms
                    </span>

                    {/* Input Tokens */}
                    <span className="inline-flex items-center gap-1 px-2 py-0.5 rounded bg-slate-800 text-slate-300 font-mono text-[11px] border border-slate-700/50">
                      <span className="text-slate-400">in:</span>
                      <span data-testid="meta-input-tokens">{meta.input_tokens}</span>
                    </span>

                    {/* Output Tokens */}
                    <span className="inline-flex items-center gap-1 px-2 py-0.5 rounded bg-slate-800 text-slate-300 font-mono text-[11px] border border-slate-700/50">
                      <span className="text-slate-400">out:</span>
                      <span data-testid="meta-output-tokens">{meta.output_tokens}</span>
                    </span>

                    {/* Failover / Key Info */}
                    {meta.key_id && (
                      <span className="inline-flex items-center gap-1 px-2 py-0.5 rounded bg-slate-800 text-slate-300 font-mono text-[11px] border border-slate-700/50">
                        <Key className="w-3 h-3 text-sky-400" />
                        {meta.key_id}
                        {meta.fallback_attempts > 0 && (
                          <span className="text-amber-400 ml-1">
                            (fallback: {meta.fallback_attempts})
                          </span>
                        )}
                      </span>
                    )}
                  </div>
                </div>
                <span className="text-[10px] text-slate-500 mt-1 ml-1">{msg.timestamp}</span>
              </div>
            );
          })
        )}

        {isLoading && (
          <div className="flex items-center space-x-2 text-slate-400 text-xs py-2 px-1">
            <div className="w-2 h-2 rounded-full bg-emerald-400 animate-ping" />
            <div className="w-2 h-2 rounded-full bg-emerald-400 animate-ping delay-100" />
            <div className="w-2 h-2 rounded-full bg-emerald-400 animate-ping delay-200" />
            <span className="text-slate-400 ml-2">Streaming through LiteLLM Gateway...</span>
          </div>
        )}
        <div ref={messagesEndRef} />
      </main>

      {/* Input Area */}
      <footer className="border-t border-slate-800 bg-slate-900/60 backdrop-blur-md p-3 sm:p-4">
        <form onSubmit={handleSend} className="max-w-4xl mx-auto flex items-end gap-2">
          <div className="relative flex-1">
            <textarea
              ref={inputRef}
              data-testid="chat-input"
              rows={1}
              value={inputMessage}
              onChange={(e) => setInputMessage(e.target.value)}
              onKeyDown={handleKeyDown}
              placeholder="Type your message... (Enter to send, Shift+Enter for new line)"
              disabled={isLoading}
              className="w-full resize-none rounded-xl bg-slate-950 border border-slate-700 px-4 py-3 text-sm text-slate-100 placeholder-slate-500 focus:outline-none focus:border-emerald-500 focus:ring-1 focus:ring-emerald-500 disabled:opacity-50 transition-all max-h-32"
            />
          </div>

          <button
            type="submit"
            data-testid="send-button"
            disabled={!inputMessage.trim() || isLoading}
            className="flex-shrink-0 h-[46px] px-5 rounded-xl bg-emerald-600 hover:bg-emerald-500 disabled:bg-slate-800 disabled:text-slate-600 text-white font-medium flex items-center justify-center transition-all shadow-md shadow-emerald-900/20"
          >
            <Send className="w-4 h-4" />
          </button>
        </form>
      </footer>
    </div>
  );
}
