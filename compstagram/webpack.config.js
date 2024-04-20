const path = require('path');

module.exports = {
    mode: 'development',  // Use 'production' for minification and optimization
    entry: './src/index.ts',  // Entry point of your application
    module: {
        rules: [
            {
                test: /\.tsx?$/,
                use: 'ts-loader',
                exclude: /node_modules/,
            },
        ],
    },
    resolve: {
        extensions: ['.tsx', '.ts', '.js'],
    },
    output: {
        filename: 'bundle.js',  // Output file
        path: path.resolve(__dirname, 'dist'),
    },
};