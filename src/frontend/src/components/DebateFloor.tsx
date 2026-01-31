import React, { useState } from 'react';
import ReactMarkdown from 'react-markdown';
import remarkGfm from 'remark-gfm';

interface DebateMessage {
    agent: string;
    content: string;
}

interface AgentConfig {
    statistics_expert: boolean;
    generalist_expert: boolean;
    devils_advocate: boolean;
    crypto_macro_analyst: boolean;
}

interface DebateResponse {
    market_id: string;
    messages: DebateMessage[];
    verdict: string;
    enabled_agents: string[];
}

interface DebateFloorProps {
    marketId: string | null;
}

/** Agent metadata for display and configuration. */
const AGENTS = [
    {
        key: 'statistics_expert' as keyof AgentConfig,
        label: 'Statistics Expert',
        emoji: '📊',
        color: 'blue',
        description: 'Analyzes price, volume, and probability'
    },
    {
        key: 'generalist_expert' as keyof AgentConfig,
        label: 'Generalist Expert',
        emoji: '🌍',
        color: 'green',
        description: 'Searches for latest news and events'
    },
    {
        key: 'crypto_macro_analyst' as keyof AgentConfig,
        label: 'Crypto/Macro Analyst',
        emoji: '📈',
        color: 'yellow',
        description: 'Provides macro and crypto context'
    },
    {
        key: 'devils_advocate' as keyof AgentConfig,
        label: "Devil's Advocate",
        emoji: '😈',
        color: 'red',
        description: 'Challenges the consensus view'
    },
];

const DebateFloor: React.FC<DebateFloorProps> = ({ marketId }) => {
    const [messages, setMessages] = useState<DebateMessage[]>([]);
    const [verdict, setVerdict] = useState<string | null>(null);
    const [isLoading, setIsLoading] = useState(false);
    const [error, setError] = useState<string | null>(null);

    // Agent toggle state
    const [agentConfig, setAgentConfig] = useState<AgentConfig>({
        statistics_expert: true,
        generalist_expert: true,
        devils_advocate: true,
        crypto_macro_analyst: true,
    });

    const API_BASE_URL = import.meta.env.VITE_API_BASE_URL || 'http://localhost:8000';

    const toggleAgent = (agentKey: keyof AgentConfig) => {
        setAgentConfig(prev => ({
            ...prev,
            [agentKey]: !prev[agentKey]
        }));
    };

    const enabledCount = Object.values(agentConfig).filter(Boolean).length;

    const initiateDebate = async () => {
        if (!marketId) return;

        setIsLoading(true);
        setError(null);
        setMessages([]);
        setVerdict(null);

        try {
            const response = await fetch(`${API_BASE_URL}/api/debate/${marketId}`, {
                method: 'POST',
                headers: {
                    'Content-Type': 'application/json',
                },
                body: JSON.stringify({
                    agents: agentConfig
                }),
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

            {/* Agent Toggle Panel */}
            <div className="p-4 bg-gray-800/40 border border-gray-700/50 rounded-2xl backdrop-blur-sm">
                <div className="flex items-center justify-between mb-3">
                    <h3 className="text-sm font-semibold text-gray-300 uppercase tracking-wide">
                        Active Agents
                    </h3>
                    <span className="text-xs text-gray-500">
                        {enabledCount}/4 enabled • Moderator always active
                    </span>
                </div>
                <div className="grid grid-cols-2 md:grid-cols-4 gap-3">
                    {AGENTS.map(agent => {
                        const isEnabled = agentConfig[agent.key];
                        const colorMap: Record<string, { bg: string; border: string; text: string }> = {
                            blue: { bg: 'bg-blue-500', border: 'border-blue-500/50', text: 'text-blue-400' },
                            green: { bg: 'bg-green-500', border: 'border-green-500/50', text: 'text-green-400' },
                            yellow: { bg: 'bg-yellow-500', border: 'border-yellow-500/50', text: 'text-yellow-400' },
                            red: { bg: 'bg-red-500', border: 'border-red-500/50', text: 'text-red-400' },
                        };
                        const colorClasses = colorMap[agent.color] ?? colorMap.blue;

                        return (
                            <button
                                key={agent.key}
                                onClick={() => toggleAgent(agent.key)}
                                disabled={isLoading}
                                className={`
                                    p-3 rounded-xl border transition-all duration-300 text-left
                                    ${isEnabled
                                        ? `${colorClasses.border} bg-gray-900/50`
                                        : 'border-gray-700/30 bg-gray-900/20 opacity-50'
                                    }
                                    ${isLoading ? 'cursor-not-allowed' : 'hover:scale-[1.02] cursor-pointer'}
                                `}
                            >
                                <div className="flex items-center gap-2 mb-1">
                                    <span className="text-lg">{agent.emoji}</span>
                                    <div className={`
                                        w-8 h-4 rounded-full transition-all duration-300 relative
                                        ${isEnabled ? colorClasses.bg : 'bg-gray-600'}
                                    `}>
                                        <div className={`
                                            absolute top-0.5 w-3 h-3 rounded-full bg-white transition-all duration-300
                                            ${isEnabled ? 'left-4' : 'left-0.5'}
                                        `} />
                                    </div>
                                </div>
                                <p className={`text-xs font-medium ${isEnabled ? colorClasses.text : 'text-gray-500'}`}>
                                    {agent.label}
                                </p>
                                <p className="text-[10px] text-gray-500 mt-0.5 line-clamp-1">
                                    {agent.description}
                                </p>
                            </button>
                        );
                    })}
                </div>
            </div>

            {error && (
                <div className="p-4 bg-red-500/10 border border-red-500/20 rounded-xl text-red-400">
                    {error}
                </div>
            )}

            {!isLoading && messages.length === 0 && !error && (
                <div className="text-center py-12 text-gray-400 bg-gray-800/30 rounded-2xl border border-gray-700/50 backdrop-blur-sm">
                    <p className="text-lg">Click "Initiate Debate" to summon the experts.</p>
                    <p className="text-sm mt-2 opacity-60">Toggle agents above to save tokens.</p>
                </div>
            )}

            {/* Verdict Card */}
            {verdict && (
                <div className="p-6 bg-gradient-to-br from-purple-900/30 to-blue-900/30 border border-purple-500/30 rounded-2xl shadow-xl backdrop-blur-md animate-slideUp">
                    <h3 className="text-xl font-bold text-white mb-4 flex items-center gap-2">
                        <span className="text-2xl">⚖️</span> Final Verdict
                    </h3>
                    <div className="prose prose-invert max-w-none text-gray-200">
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
                                        : 'bg-gray-800/40 border-gray-600/30 mx-6'
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
                                <ReactMarkdown remarkPlugins={[remarkGfm]}>
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
