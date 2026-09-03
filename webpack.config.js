const path = require('path');
const webpack = require('webpack');
const HtmlWebpackPlugin = require('html-webpack-plugin');

module.exports = (env, argv) => {
  const isDev = argv.mode !== 'production';
  const backendProxyTarget =
    process.env.STREAMHUB_BACKEND_PROXY_TARGET || 'http://127.0.0.1:8100';

  return {
    mode: isDev ? 'development' : 'production',
    entry: './src/index.tsx',
    output: {
      path: path.resolve(__dirname, 'dist'),
      filename: 'bundle.js',
      // 绝对路径：让 /watch/<id>、/admin/videos 等深层路由在刷新/直达时仍能加载到
      // /bundle.js，而不是相对解析成 /watch/bundle.js 导致 404 白屏。
      publicPath: '/'
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

      proxy: [
        {
          pathFilter: ['/uploads', '/avatars'],
          target: backendProxyTarget,
          changeOrigin: true,
        },
      ],

      hot: false,
      liveReload: false,

      client: {
        overlay: false,
        reconnect: false,
        webSocketURL: {
          hostname: 'localhost',
          port: 5273,
          pathname: '/ws',
          protocol: 'ws',
        },
      },

    },
    plugins: [
      new webpack.DefinePlugin({
        __STREAMHUB_API_BASE_URL__: JSON.stringify(
          process.env.REACT_APP_API_BASE_URL || 'http://127.0.0.1:8100'
        ),
      }),
      new HtmlWebpackPlugin({
        template: './index.html',
        inject: 'body'
      })
    ]
  };
};
