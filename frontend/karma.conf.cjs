module.exports = config => config.set({
  frameworks: ['jasmine', '@angular-devkit/build-angular'],
  plugins: [
    require('karma-jasmine'),
    require('karma-chrome-launcher'),
    require('@angular-devkit/build-angular/plugins/karma'),
  ],
  reporters: ['progress'],
  port: 9876,
  hostname: '0.0.0.0',
  browsers: [], // Attach an existing browser; CI can pass --browsers=ChromeHeadless.
  singleRun: true,
  client: { clearContext: false },
  browserNoActivityTimeout: 30000,
});
