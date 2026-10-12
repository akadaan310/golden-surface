package com.goldenmotion
import android.app.Application
import com.facebook.react.PackageList
import com.facebook.react.ReactApplication
import com.facebook.react.ReactNativeHost
import com.facebook.react.ReactHost
import com.facebook.react.defaults.DefaultReactNativeHost
import com.facebook.react.defaults.DefaultReactHost.getDefaultReactHost
import com.facebook.react.soloader.OpenSourceMergedSoMapping
import com.facebook.soloader.SoLoader
class MainApplication:Application(),ReactApplication {
 override val reactNativeHost:ReactNativeHost=object:DefaultReactNativeHost(this){override fun getPackages()=PackageList(this).packages.apply{add(HardwarePackage())};override fun getJSMainModuleName()="index";override fun getUseDeveloperSupport()=BuildConfig.DEBUG;override val isNewArchEnabled=false;override val isHermesEnabled=true}
 override val reactHost:ReactHost get()=getDefaultReactHost(applicationContext,reactNativeHost)
 override fun onCreate(){super.onCreate();SoLoader.init(this,OpenSourceMergedSoMapping)}
}
