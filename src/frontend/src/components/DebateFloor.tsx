import React, { useState } from 'react';
import ReactMarkdown from 'react-markdown';
import remarkGfm from 'remark-gfm';

interface DebateMessage {
    agent: string;
    content: string;
}

interface DebateResponse {
    market_id: string;
    messages: DebateMessage[];
    verdict: string;
}

interface DebateFloorProps {
    marketId: string | null;
}

const DebateFloor: React.FC<DebateFloorProps> = ({ marketId }) => {
    const [messages, setMessages] = useState<DebateMessage[]>([]);
    const [verdict, setVerdict] = useState<string | null>(null);
    const [isLoading, setIsLoading] = useState(false);
    const [error, setError] = useState<string | null>(null);

    const API_BASE_URL = import.meta.env.VITE_API_BASE_URL || 'http://localhost:8000';

    const initiateDebate = async () => {
        if (!marketId) return;

        setIsLoading(true);
        setError(null);
        setMessages([]);
        setVerdict(null);

        try {
            const response = await fetch(`${API_BASE_URL}/api/debate/${marketId}`, {
                method: 'POST',
            });

            if (!response.ok) {
                const errData = await response.json();
                throw new Error(errData.detail || 'Failed to initiate debate');
            }

            const data: DebateResponse = await response.json();
            setMessages(data.messages);
            setVerdict(data.verdict);
        } catch (err: any) {
            setError(err.message);
        } finally {
            setIsLoading(false);
        }
    };

    if (!marketId) {
        return (
            <div className="flex items-center justify-center h-64 text-gray-400">
                Select a market to enter the Debate Floor
            </div>
        );
    }

    return (
        <div className="flex flex-col space-y-6 animate-fadeIn">
            <div className="flex items-center justify-between">
                <h2 className="text-2xl font-bold bg-gradient-to-r from-blue-400 to-purple-500 bg-clip-text text-transparent">
                    AI Debate Floor
                </h2>
                <button
                    onClick={initiateDebate}
                    disabled={isLoading}
                    className={`px-6 py-2 rounded-xl font-semibold transition-all duration-300 ${isLoading
                        ? 'bg-gray-700 text-gray-400 cursor-not-allowed'
                        : 'bg-gradient-to-r from-blue-600 to-purple-600 hover:from-blue-500 hover:to-purple-500 text-white shadow-lg hover:shadow-blue-500/25'
                        }`}
                >
                    {isLoading ? 'Agents Debating...' : messages.length > 0 ? 'Restart Debate' : 'Initiate Debate'}
                </button>
            </div>

            {error && (
                <div className="p-4 bg-red-500/10 border border-red-500/20 rounded-xl text-red-400">
                    {error}
                </div>
            )}

            {!isLoading && messages.length === 0 && !error && (
                <div className="text-center py-12 text-gray-400 bg-gray-800/30 rounded-2xl border border-gray-700/50 backdrop-blur-sm">
                    <p className="text-lg">Click "Initiate Debate" to summon the experts.</p>
                    <p className="text-sm mt-2 opacity-60">Cost-effective analysis on demand.</p>
                </div>
            )}

            {/* Verdict Card */}
            {verdict && (
                <div className="p-6 bg-gradient-to-br from-purple-900/30 to-blue-900/30 border border-purple-500/30 rounded-2xl shadow-xl backdrop-blur-md animate-slideUp">
                    <h3 className="text-xl font-bold text-white mb-4 flex items-center gap-2">
                        <span className="text-2xl">⚖️</span> Final Verdict
                    </h3>
                    <div className="prose prose-invert max-w-none text-gray-200">
                        {/* Markdown rendering */}
                        <ReactMarkdown remarkPlugins={[remarkGfm]}>
                            {verdict}
                        </ReactMarkdown>
                    </div>
                </div>
            )}

            {/* Conversation Stream */}
            <div className="space-y-4">
                {messages.map((msg, idx) => (
                    <div
                        key={idx}
                        className={`p-5 rounded-2xl border backdrop-blur-sm transition-all duration-500 animate-slideInLeft ${msg.agent === 'Statistics Expert'
                            ? 'bg-blue-900/20 border-blue-500/30 ml-0 mr-12'
                            : msg.agent === 'Generalist Expert'
                                ? 'bg-green-900/20 border-green-500/30 ml-4 mr-8'
                                : msg.agent === "Devil's Advocate"
                                    ? 'bg-red-900/20 border-red-500/30 ml-8 mr-4'
                                    : msg.agent === 'Crypto/Macro Analyst'
                                        ? 'bg-yellow-900/20 border-yellow-500/30 ml-12 mr-0'
                                        : 'bg-gray-800/40 border-gray-600/30 mx-6' // Moderator or others
                            }`}
                        style={{ animationDelay: `${idx * 0.1}s` }}
                    >
                        <div className="flex items-center gap-3 mb-2">
                            <span className="text-xl">
                                {msg.agent === 'Statistics Expert' && '📊'}
                                {msg.agent === 'Generalist Expert' && '🌍'}
                                {msg.agent === "Devil's Advocate" && '😈'}
                                {msg.agent === 'Crypto/Macro Analyst' && '📈'}
                                {msg.agent === 'Moderator' && '👨‍⚖️'}
                            </span>
                            <span className={`font-bold ${msg.agent === 'Statistics Expert' ? 'text-blue-400' :
                                msg.agent === 'Generalist Expert' ? 'text-green-400' :
                                    msg.agent === "Devil's Advocate" ? 'text-red-400' :
                                        msg.agent === 'Crypto/Macro Analyst' ? 'text-yellow-400' :
                                            'text-purple-400'
                                }`}>
                                {msg.agent}
                            </span>
                        </div>
                        <div className="text-gray-300 leading-relaxed text-sm">
                            <div className="prose prose-invert max-w-none prose-sm prose-p:my-1 prose-headings:my-2 prose-ul:my-1">
                                <ReactMarkdown
                                    remarkPlugins={[remarkGfm]}
                                >
                                    {msg.content}
                                </ReactMarkdown>
                            </div>
                        </div>
                    </div>
                ))}
            </div>

            {isLoading && (
                <div className="flex justify-center items-center py-12">
                    <div className="animate-pulse flex flex-col items-center gap-4">
                        <div className="h-4 w-4 bg-blue-500 rounded-full animate-bounce"></div>
                        <span className="text-blue-400 font-medium">Experts are deliberating...</span>
                    </div>
                </div>
            )}
        </div>
    );
};

export default DebateFloor;
