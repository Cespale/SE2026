import React, { useRef, useState } from 'react';
import { useNavigate } from 'react-router-dom';
import { motion } from 'framer-motion';
import { Upload, Loader2, CheckCircle, Film, ImageIcon, X } from 'lucide-react';
import { useVideoStore } from '../stores/videoStore';
import { API_BASE } from '../api';

export const UploadPage: React.FC = () => {
  const navigate = useNavigate();
  const { uploadVideo, categories, fetchCategories } = useVideoStore();
  const fileInputRef = useRef<HTMLInputElement>(null);
  const coverInputRef = useRef<HTMLInputElement>(null);

  const [title, setTitle] = useState('');
  const [description, setDescription] = useState('');
  const [categoryId, setCategoryId] = useState('1');
  
  const [isUploading, setIsUploading] = useState(false);
  const [uploadProgress, setUploadProgress] = useState(0);
  const [uploadedVideoUrl, setUploadedVideoUrl] = useState('');
  const [uploadedVideoDuration, setUploadedVideoDuration] = useState(0);
  const [autoCoverUrl, setAutoCoverUrl] = useState('');
  
  const [customCoverFile, setCustomCoverFile] = useState<File | null>(null);
  const [customCoverPreview, setCustomCoverPreview] = useState('');
  const [isUploadingCover, setIsUploadingCover] = useState(false);
  const [finalCoverUrl, setFinalCoverUrl] = useState('');
  
  const [isSubmitting, setIsSubmitting] = useState(false);
  const [success, setSuccess] = useState(false);

  React.useEffect(() => {
    fetchCategories();
  }, []);

  const normalCategories = categories.filter(c => c.type === 0);

  const getAuthToken = () => {
    const token = localStorage.getItem('auth-storage');
    if (token) {
      try {
        const parsed = JSON.parse(token);
        return parsed.state?.token || '';
      } catch (e) {
        return '';
      }
    }
    return '';
  };

  // 上传视频
  const handleVideoSelect = async (e: React.ChangeEvent<HTMLInputElement>) => {
    const file = e.target.files?.[0];
    if (!file) return;

    if (!file.type.startsWith('video/')) {
      alert('请选择视频文件');
      return;
    }

    if (file.size > 500 * 1024 * 1024) {
      alert('文件大小不能超过500MB');
      return;
    }

    if (!title.trim()) {
      setTitle(file.name.replace(/\.[^/.]+$/, ''));
    }

    setIsUploading(true);
    setUploadProgress(0);

    const formData = new FormData();
    formData.append('file', file);

    const xhr = new XMLHttpRequest();
    xhr.upload.onprogress = (event) => {
      if (event.lengthComputable) {
        setUploadProgress(Math.round((event.loaded / event.total) * 100));
      }
    };
    xhr.onload = () => {
      if (xhr.status === 200) {
        const response = JSON.parse(xhr.responseText);
        setUploadedVideoUrl(response.data.videoUrl);
        setUploadedVideoDuration(response.data.duration || 60);
        setAutoCoverUrl(response.data.coverUrl || '');
        setFinalCoverUrl(response.data.coverUrl || '');
        setIsUploading(false);
      } else {
        alert('上传失败');
        setIsUploading(false);
      }
    };
    xhr.onerror = () => {
      alert('网络错误');
      setIsUploading(false);
    };
    xhr.open('POST', `${API_BASE}/api/videos/upload-file`);
    xhr.setRequestHeader('Authorization', `Bearer ${getAuthToken()}`);
    xhr.send(formData);
  };

  // 上传自定义封面
  const handleCoverSelect = async (e: React.ChangeEvent<HTMLInputElement>) => {
    const file = e.target.files?.[0];
    if (!file) return;

    if (!file.type.startsWith('image/')) {
      alert('请选择图片文件');
      return;
    }

    if (file.size > 5 * 1024 * 1024) {
      alert('图片大小不能超过5MB');
      return;
    }

    setCustomCoverFile(file);
    const previewUrl = URL.createObjectURL(file);
    setCustomCoverPreview(previewUrl);
    
    setIsUploadingCover(true);
    const formData = new FormData();
    formData.append('file', file);
    
    try {
      const response = await fetch(`${API_BASE}/api/videos/upload-cover`, {
        method: 'POST',
        headers: {
          'Authorization': `Bearer ${getAuthToken()}`
        },
        body: formData
      });
      const data = await response.json();
      if (response.ok) {
        setFinalCoverUrl(data.data.coverUrl);
      } else {
        alert('封面上传失败');
        setCustomCoverPreview('');
        setCustomCoverFile(null);
        setFinalCoverUrl(autoCoverUrl);
      }
    } catch (err) {
      alert('封面上传失败');
      setCustomCoverPreview('');
      setCustomCoverFile(null);
      setFinalCoverUrl(autoCoverUrl);
    } finally {
      setIsUploadingCover(false);
    }
  };

  // 移除自定义封面
  const removeCustomCover = () => {
    if (customCoverPreview) {
      URL.revokeObjectURL(customCoverPreview);
    }
    setCustomCoverFile(null);
    setCustomCoverPreview('');
    setFinalCoverUrl(autoCoverUrl);
    if (coverInputRef.current) {
      coverInputRef.current.value = '';
    }
  };

  // 发布视频
  const handleSubmit = async () => {
    if (!title.trim()) {
      alert('请填写标题');
      return;
    }
    if (!uploadedVideoUrl) {
      alert('请先上传视频');
      return;
    }

    setIsSubmitting(true);
    const result = await uploadVideo({
      title: title.trim(),
      description: description.trim() || '无简介',
      categoryId,
      tags: [],
      coverUrl: finalCoverUrl,
      videoUrl: uploadedVideoUrl,
      duration: uploadedVideoDuration,
    });
    setIsSubmitting(false);

    if (result) {
      setSuccess(true);
      setTimeout(() => navigate('/creator'), 2000);
    } else {
      alert('发布失败');
    }
  };

  const resetForm = () => {
    setTitle('');
    setDescription('');
    setCategoryId('1');
    setUploadedVideoUrl('');
    setUploadedVideoDuration(0);
    setAutoCoverUrl('');
    setFinalCoverUrl('');
    if (customCoverPreview) {
      URL.revokeObjectURL(customCoverPreview);
    }
    setCustomCoverFile(null);
    setCustomCoverPreview('');
    if (fileInputRef.current) fileInputRef.current.value = '';
    if (coverInputRef.current) coverInputRef.current.value = '';
    setSuccess(false);
  };

  if (success) {
    return (
      <div className="min-h-screen bg-gray-50 dark:bg-gray-900 py-8">
        <div className="max-w-7xl mx-auto px-4">
          <div className="bg-white dark:bg-gray-800 rounded-2xl p-10 text-center w-full">
            <CheckCircle className="w-16 h-16 text-green-500 mx-auto mb-4" />
            <h2 className="text-xl font-bold mb-2">发布成功！</h2>
            <p className="text-gray-500 mb-6">视频已提交审核</p>
            <button onClick={() => navigate('/creator')} className="px-6 py-2 bg-blue-500 text-white rounded-lg">
              去创作者中心
            </button>
          </div>
        </div>
      </div>
    );
  }

  const isVideoUploaded = !!uploadedVideoUrl;

  return (
    <div className="min-h-screen bg-gray-50 dark:bg-gray-900 py-8">
      <div className="max-w-7xl mx-auto px-4">
        <h1 className="text-2xl font-bold mb-8">上传视频</h1>

        <motion.div className="bg-white dark:bg-gray-800 rounded-2xl p-8 space-y-6 w-full">
          {/* 视频上传区域 */}
          <div>
            <label className="block text-sm font-medium mb-2">视频文件 *</label>
            {!isVideoUploaded ? (
              <div
                onClick={() => fileInputRef.current?.click()}
                className="border-2 border-dashed rounded-lg p-8 text-center cursor-pointer hover:border-blue-500"
              >
                {isUploading ? (
                  <div>
                    <Loader2 className="w-10 h-10 text-blue-500 animate-spin mx-auto mb-3" />
                    <p>上传中 {uploadProgress}%</p>
                    <div className="w-full bg-gray-200 rounded-full h-2 mt-2">
                      <div className="bg-blue-500 h-2 rounded-full" style={{ width: `${uploadProgress}%` }} />
                    </div>
                  </div>
                ) : (
                  <>
                    <Upload className="w-12 h-12 text-gray-400 mx-auto mb-3" />
                    <p>点击选择视频文件</p>
                    <p className="text-xs text-gray-400 mt-1">MP4、MOV、AVI，最大500MB</p>
                  </>
                )}
                <input ref={fileInputRef} type="file" accept="video/*" onChange={handleVideoSelect} className="hidden" disabled={isUploading} />
              </div>
            ) : (
              <div>
                <div className="p-3 bg-green-50 rounded-lg border border-green-200 mb-4">
                  <Film className="w-5 h-5 text-green-600 inline mr-2" />
                  <span className="text-sm">视频已上传</span>
                  <button
                    onClick={() => {
                      setUploadedVideoUrl('');
                      setAutoCoverUrl('');
                      setFinalCoverUrl('');
                      removeCustomCover();
                      if (fileInputRef.current) fileInputRef.current.value = '';
                    }}
                    className="ml-4 text-red-500 text-sm hover:text-red-700"
                  >
                    重新选择
                  </button>
                </div>

                {/* 封面预览 - 16:9 视频比例 */}
                <div className="mt-4">
                  <label className="block text-sm font-medium mb-2">封面</label>
                  <div className="relative w-64">
                    <div className="aspect-video bg-gray-100 rounded-lg overflow-hidden border">
                      {customCoverPreview ? (
                        <img
                          src={customCoverPreview}
                          alt="自定义封面"
                          className="w-full h-full object-cover"
                        />
                      ) : autoCoverUrl ? (
                        <img
                          src={autoCoverUrl}
                          alt="自动生成的封面"
                          className="w-full h-full object-cover"
                        />
                      ) : (
                        <div className="w-full h-full flex items-center justify-center">
                          <ImageIcon className="w-8 h-8 text-gray-400" />
                        </div>
                      )}
                    </div>
                  </div>
                  
                  {/* 选择自定义封面按钮 */}
                  <div className="mt-3">
                    <div className="flex gap-2">
                      <input
                        ref={coverInputRef}
                        type="file"
                        accept="image/jpeg,image/png,image/jpg"
                        onChange={handleCoverSelect}
                        className="hidden"
                      />
                      <button
                        type="button"
                        onClick={() => coverInputRef.current?.click()}
                        disabled={isUploadingCover}
                        className="px-4 py-2 border rounded-lg hover:bg-gray-50 flex items-center gap-2 text-sm"
                      >
                        {isUploadingCover ? (
                          <Loader2 className="w-4 h-4 animate-spin" />
                        ) : (
                          <ImageIcon className="w-4 h-4" />
                        )}
                        {isUploadingCover ? '上传中...' : customCoverPreview ? '更换封面' : '选择自定义封面'}
                      </button>
                      {customCoverPreview && (
                        <button
                          onClick={removeCustomCover}
                          className="px-4 py-2 border rounded-lg hover:bg-gray-50 text-sm text-red-500"
                        >
                          恢复默认
                        </button>
                      )}
                    </div>
                  </div>
                </div>
              </div>
            )}
          </div>

          {/* 标题 */}
          <div>
            <label className="block text-sm font-medium mb-2">标题 *</label>
            <input
              type="text"
              value={title}
              onChange={(e) => setTitle(e.target.value)}
              className="w-full px-4 py-2 border rounded-lg"
              placeholder="输入标题"
            />
          </div>

          {/* 简介 */}
          <div>
            <label className="block text-sm font-medium mb-2">简介</label>
            <textarea
              value={description}
              onChange={(e) => setDescription(e.target.value)}
              rows={4}
              className="w-full px-4 py-2 border rounded-lg resize-none"
              placeholder="介绍你的视频..."
            />
          </div>

          {/* 分类 */}
          <div>
            <label className="block text-sm font-medium mb-2">分类 *</label>
            <select
                value={categoryId}
                onChange={(e) => setCategoryId(e.target.value)}
                className="w-full px-4 py-2 border rounded-lg"
              >
                {normalCategories
                  .filter(cat => cat.name !== '推荐')
                  .map(cat => (
                    <option key={cat.id} value={cat.id}>{cat.name}</option>
                  ))}
              </select>
          </div>

          {/* 按钮 */}
          <div className="flex gap-4 pt-4">
            <button onClick={resetForm} className="flex-1 py-3 border rounded-lg hover:bg-gray-50">
              重置
            </button>
            <button
              onClick={handleSubmit}
              disabled={!uploadedVideoUrl || isSubmitting}
              className="flex-1 py-3 bg-blue-500 text-white rounded-lg hover:bg-blue-600 disabled:opacity-50"
            >
              {isSubmitting ? '发布中...' : '发布视频'}
            </button>
          </div>
        </motion.div>
      </div>
    </div>
  );
};

export default UploadPage;
