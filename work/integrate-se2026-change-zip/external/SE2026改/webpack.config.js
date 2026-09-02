const path = require('path');
const webpack = require('webpack');
const HtmlWebpackPlugin = require('html-webpack-plugin');

module.exports = (env, argv) => {
  const isDev = argv.mode !== 'production';
  const backendProxyTarget =
    process.env.STREAMHUB_BACKEND_PROXY_TARGET || 'http://127.0.0.1:8000';

  return {
    mode: isDev ? 'development' : 'production',
    entry: './src/index.tsx',
    output: {
      path: path.resolve(__dirname, 'dist'),
      filename: 'bundle.js',
      publicPath: 'auto'
    },
    module: {
      rules: [
        {
          test: /\.mjs$/,
          include: /node_modules/,
          type: 'javascript/auto',
          resolve: {
            fullySpecified: false,
          },
        },
        {
          test: /\.(ts|tsx|js|jsx)$/,
          exclude: /node_modules/,
          use: {
            loader: 'babel-loader',
            options: {
              presets: [
                [
                  '@babel/preset-react',
                  {
                    runtime: 'automatic',
                    development: isDev
                  }
                ],
                '@babel/preset-env',
                '@babel/preset-typescript'
              ]
            }
          }
        },
        {
          test: /\.css$/,
          use: ['style-loader', 'css-loader', 'postcss-loader']
        },
        {
          test: /\.(png|jpe?g|gif|webp|ico|svg)$/i,
          type: 'asset',
          parser: { dataUrlCondition: { maxSize: 8 * 1024 } }
        },
        {
          test: /\.(woff2?|eot|ttf|otf)$/i,
          type: 'asset/resource'
        },
        {
          // 兜底规则：PDF、文档、音视频等所有其他文件一律输出为独立资源文件
          exclude: /\.(js|jsx|ts|tsx|mjs|css|json|html)$/i,
          type: 'asset/resource'
        }
      ]
    },
    resolve: {
      extensions: ['.mjs', '.ts', '.tsx', '.js', '.jsx']
    },
    devServer: {
      host: '0.0.0.0',
      port: 3266,

      static: {
        directory: path.join(__dirname, 'public'),
        watch: false,
      },

      historyApiFallback: true,
      allowedHosts: 'all',

      proxy: {
        '/uploads': {
          target: backendProxyTarget,
          changeOrigin: true,
        },
        '/avatars': {
          target: backendProxyTarget,
          changeOrigin: true,
        },
        '/api': {
          target: backendProxyTarget,
          changeOrigin: true,
        },
        // 业务 WebSocket 必须转发到后端,否则 /ws/chat、/ws/live 会被 dev-server 自身的
        // HMR socket（精确匹配 /ws）拒绝,私信/弹幕无法实时收发。ws:true 开启 upgrade 转发。
        // 注意:不能代理整段 /ws——HMR 客户端也连 /ws,整段代理会把它劫持转发到后端,
        // 后端没有 /ws 路由,返回普通 HTTP 响应导致 "Invalid frame header"。
        '/ws/chat': {
          target: backendProxyTarget,
          changeOrigin: true,
          ws: true,
        },
        '/ws/live': {
          target: backendProxyTarget,
          changeOrigin: true,
          ws: true,
        },
      },

      hot: false,
      liveReload: false,

      client: {
        overlay: false,
        reconnect: false,
        webSocketURL: {
          // port 0 = 跟随页面实际访问端口（location.port），
          // 适配 K8s port-forward / docker compose / 本地 dev 等任意访问方式
          port: 0,
        },
      },

      watchFiles: {
        paths: ['src/**/*'],
        options: {
          ignored: ['**/public/**', '**/node_modules/**'],
          usePolling: false,
        },
      },
    },
    plugins: [
      new webpack.DefinePlugin({
        __STREAMHUB_API_BASE_URL__: JSON.stringify(
          process.env.REACT_APP_API_BASE_URL || ''
        ),
      }),
      new HtmlWebpackPlugin({
        template: './index.html',
        inject: 'body'
      })
    ]
  };
};
