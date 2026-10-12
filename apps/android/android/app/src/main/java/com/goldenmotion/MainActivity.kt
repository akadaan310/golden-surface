package com.goldenmotion
import com.facebook.react.ReactActivity
import com.facebook.react.ReactActivityDelegate
import com.facebook.react.defaults.DefaultReactActivityDelegate
class MainActivity:ReactActivity(){override fun getMainComponentName()="GoldenMotion";override fun createReactActivityDelegate():ReactActivityDelegate=DefaultReactActivityDelegate(this,mainComponentName,false)}
