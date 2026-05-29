import React, { useEffect, useMemo, useRef, useState } from 'react';
import { useLocation, useNavigate } from 'react-router-dom';
import { Send, RotateCcw, MessageCircle } from 'lucide-react';
import { useChatStore } from '../stores/chatStore';
import { useAuthStore } from '../stores/authStore';

function timeAgo(iso: string): string {
  if (!iso) return '';
  const t = new Date(iso).getTime();
  const diff = Date.now() - t;
  if (diff < 60_000) return '刚刚';
  if (diff < 3_600_000) return `${Math.floor(diff / 60_000)} 分钟前`;
  if (diff < 86_400_000) return `${Math.floor(diff / 3_600_000)} 小时前`;
  return new Date(iso).toLocaleDateString();
}

function formatTime(iso: string): string {
  if (!iso) return '';
  const d = new Date(iso);
  return d.toLocaleTimeString([], { hour: '2-digit', minute: '2-digit' });
}

export function MessagePage() {
  const navigate = useNavigate();
  const location = useLocation();
  const { user, token } = useAuthStore() as any;
  const {
    ws, myUserId, conversations, messagesByConv, activeConvId,
    connect, loadConversations, openConversationWith, selectConversation,
    sendText, recall,
  } = useChatStore();

  const [input, setInput] = useState('');
  const scrollRef = useRef<HTMLDivElement>(null);

  // 连接 WS
  useEffect(() => {
    if (token && !ws) connect(token);
  }, [token]);

  // 加载会话列表
  useEffect(() => {
    loadConversations();
  }, []);

  // 处理 ?peer=xxx 参数:从用户主页"发消息"按钮跳进来,自动打开会话
  useEffect(() => {
    const params = new URLSearchParams(location.search);
    const peerId = params.get('peer');
    if (peerId) {
      openConversationWith(peerId).then((c) => selectConversation(c.id));
    }
  }, [location.search]);

  // 自动滚到底部
  const activeMessages = activeConvId ? messagesByConv[activeConvId] || [] : [];
  useEffect(() => {
    scrollRef.current?.scrollTo({ top: scrollRef.current.scrollHeight, behavior: 'smooth' });
  }, [activeMessages.length, activeConvId]);

  const activeConv = useMemo(
    () => conversations.find((c) => c.id === activeConvId) || null,
    [conversations, activeConvId]
  );

  function handleSend() {
    if (!activeConv || !input.trim()) return;
    sendText(activeConv.peerId, input);
    setInput('');
  }

  return (
    <div className="min-h-[calc(100vh-4rem)] bg-gray-50 dark:bg-gray-900">
      <div className="max-w-6xl mx-auto h-[calc(100vh-4rem)] flex">
        {/* 左侧:会话列表 */}
        <aside className="w-72 bg-white dark:bg-gray-800 border-r border-gray-200 dark:border-gray-700 flex flex-col">
          <div className="p-4 border-b border-gray-200 dark:border-gray-700">
            <h2 className="font-bold text-gray-900 dark:text-white flex items-center gap-2">
              <MessageCircle className="w-5 h-5" />
              私信
            </h2>
            <p className="text-xs text-gray-400 mt-1">
              {ws ? '🟢 实时连接' : '⚪ 连接中...'}
            </p>
          </div>
          <div className="flex-1 overflow-y-auto">
            {conversations.length === 0 && (
              <div className="text-center text-gray-400 py-10 text-sm">
                暂无会话
                <br />
                去用户主页点 "发消息" 开始
              </div>
            )}
            {conversations.map((c) => (
              <div
                key={c.id}
                onClick={() => selectConversation(c.id)}
                className={`flex items-center gap-3 p-3 cursor-pointer border-b border-gray-100 dark:border-gray-700 ${
                  activeConvId === c.id
                    ? 'bg-blue-50 dark:bg-blue-900/20'
                    : 'hover:bg-gray-50 dark:hover:bg-gray-700'
                }`}
              >
                <div className="relative">
                  <img src={c.peerAvatar} alt={c.peerName} className="w-10 h-10 rounded-full" />
                  {c.unreadCount > 0 && (
                    <span className="absolute -top-1 -right-1 min-w-[18px] h-[18px] px-1 text-[10px] font-bold text-white bg-red-500 rounded-full flex items-center justify-center">
                      {c.unreadCount > 99 ? '99+' : c.unreadCount}
                    </span>
                  )}
                </div>
                <div className="flex-1 min-w-0">
                  <div className="flex items-baseline justify-between">
                    <div className="font-medium text-sm text-gray-900 dark:text-white truncate">
                      {c.peerName}
                    </div>
                    <div className="text-[10px] text-gray-400 whitespace-nowrap">
                      {timeAgo(c.lastMessageAt)}
                    </div>
                  </div>
                  <div className="text-xs text-gray-500 truncate mt-0.5">
                    {c.lastMessage || '开始聊天吧'}
                  </div>
                </div>
              </div>
            ))}
          </div>
        </aside>

        {/* 右侧:聊天窗口 */}
        <section className="flex-1 flex flex-col bg-white dark:bg-gray-800">
          {!activeConv ? (
            <div className="flex-1 flex items-center justify-center text-gray-400">
              <div className="text-center">
                <MessageCircle className="w-16 h-16 mx-auto mb-4 opacity-30" />
                <p>选择一个会话开始聊天</p>
              </div>
            </div>
          ) : (
            <>
              <div className="px-6 py-4 border-b border-gray-200 dark:border-gray-700 flex items-center gap-3">
                <img
                  src={activeConv.peerAvatar}
                  alt={activeConv.peerName}
                  className="w-9 h-9 rounded-full cursor-pointer"
                  onClick={() => navigate(`/user/${activeConv.peerId}`)}
                />
                <div
                  className="font-semibold text-gray-900 dark:text-white cursor-pointer"
                  onClick={() => navigate(`/user/${activeConv.peerId}`)}
                >
                  {activeConv.peerName}
                </div>
              </div>

              <div ref={scrollRef} className="flex-1 overflow-y-auto p-6 space-y-3">
                {activeMessages.map((m) => {
                  const mine = m.senderId === myUserId;
                  return (
                    <div key={m.id} className={`flex ${mine ? 'justify-end' : 'justify-start'} group`}>
                      {!mine && (
                        <img src={m.senderAvatar} alt={m.senderName} className="w-8 h-8 rounded-full mr-2" />
                      )}
                      <div className={`max-w-[60%] ${mine ? 'items-end' : 'items-start'} flex flex-col`}>
                        <div
                          className={`px-3 py-2 rounded-2xl text-sm ${
                            m.isRecalled
                              ? 'bg-gray-200 dark:bg-gray-700 text-gray-500 italic'
                              : mine
                              ? 'bg-blue-500 text-white'
                              : 'bg-gray-100 dark:bg-gray-700 text-gray-900 dark:text-white'
                          }`}
                        >
                          {m.content}
                        </div>
                        <div className="flex items-center gap-2 mt-1 text-[10px] text-gray-400">
                          <span>{formatTime(m.createTime)}</span>
                          {mine && !m.isRecalled && (
                            <button
                              onClick={() => recall(m.id)}
                              className="opacity-0 group-hover:opacity-100 hover:text-red-500 flex items-center gap-0.5"
                              title="撤回(2分钟内)"
                            >
                              <RotateCcw className="w-3 h-3" />
                              撤回
                            </button>
                          )}
                          {mine && m.isRead && !m.isRecalled && <span>已读</span>}
                        </div>
                      </div>
                    </div>
                  );
                })}
                {activeMessages.length === 0 && (
                  <div className="text-center text-gray-400 py-20 text-sm">还没有消息,打个招呼吧 👋</div>
                )}
              </div>

              <div className="px-4 py-3 border-t border-gray-200 dark:border-gray-700 flex gap-2">
                <input
                  type="text"
                  value={input}
                  onChange={(e) => setInput(e.target.value)}
                  onKeyDown={(e) => {
                    if (e.key === 'Enter') handleSend();
                  }}
                  placeholder="输入消息..."
                  className="flex-1 px-4 py-2 bg-gray-100 dark:bg-gray-700 rounded-full focus:ring-2 focus:ring-blue-500 outline-none text-gray-900 dark:text-white"
                />
                <button
                  onClick={handleSend}
                  className="px-4 py-2 bg-blue-500 text-white rounded-full hover:bg-blue-600 flex items-center gap-1"
                >
                  <Send className="w-4 h-4" />
                  发送
                </button>
              </div>
            </>
          )}
        </section>
      </div>
    </div>
  );
}
