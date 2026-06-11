import React, { useState } from 'react';
import { X } from 'lucide-react';
import { apiRequest } from '../api';

interface ReportModalProps {
  isOpen: boolean;
  onClose: () => void;
  targetType: number; // 0视频 1评论 2直播
  targetId: string;
  onSuccess?: () => void;
}

export function ReportModal({ isOpen, onClose, targetType, targetId, onSuccess }: ReportModalProps) {
  const [reason, setReason] = useState('');
  const [isSubmitting, setIsSubmitting] = useState(false);
  const [error, setError] = useState('');

  if (!isOpen) return null;

  const handleSubmit = async () => {
    if (!reason.trim()) {
      setError('请填写举报理由');
      return;
    }
    if (reason.length > 500) {
      setError('举报理由不能超过500字');
      return;
    }

    setIsSubmitting(true);
    setError('');

    try {
      await apiRequest('/api/reports', {
        method: 'POST',
        body: JSON.stringify({
          target_type: targetType,
          target_id: targetId,
          reason: reason.trim()
        })
      });
      onSuccess?.();
      onClose();
      alert('举报已提交，感谢您的反馈');
    } catch (err) {
      setError('提交失败，请稍后重试');
    } finally {
      setIsSubmitting(false);
    }
  };

  return (
    <div className="fixed inset-0 bg-black/50 flex items-center justify-center z-50" onClick={onClose}>
      <div className="bg-white dark:bg-gray-800 rounded-2xl p-6 w-full max-w-md" onClick={(e) => e.stopPropagation()}>
        <div className="flex items-center justify-between mb-4">
          <h2 className="text-xl font-bold text-gray-900 dark:text-white">举报</h2>
          <button onClick={onClose} className="p-1 hover:bg-gray-100 rounded-lg">
            <X className="w-5 h-5" />
          </button>
        </div>
        
        <div className="mb-4">
          <label className="block text-sm font-medium mb-2 text-gray-900 dark:text-white">举报理由</label>
          <textarea
            value={reason}
            onChange={(e) => setReason(e.target.value)}
            rows={4}
            className="w-full px-4 py-2 border rounded-lg resize-none"
            placeholder="请描述举报原因..."
          />
          <p className="text-xs text-gray-500 mt-1">{reason.length}/500</p>
        </div>
        
        {error && <p className="text-red-500 text-sm mb-4">{error}</p>}
        
        <div className="flex gap-3">
          <button onClick={onClose} className="flex-1 px-4 py-2 border rounded-lg hover:bg-gray-50">
            取消
          </button>
          <button
            onClick={handleSubmit}
            disabled={isSubmitting}
            className="flex-1 px-4 py-2 bg-red-500 text-white rounded-lg hover:bg-red-600 disabled:opacity-50"
          >
            {isSubmitting ? '提交中...' : '提交'}
          </button>
        </div>
      </div>
    </div>
  );
}