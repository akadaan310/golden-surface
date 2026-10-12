package com.goldenmotion
object AcquisitionPolicy {
 fun duration(value:Double):Long=if(value.isFinite())value.toLong().coerceIn(500,5000)else 3000
 fun amplitude(value:Double):Double=if(value.isFinite())value.coerceIn(0.0,0.01)else 0.01
 fun frequency(value:Double):Double=if(value.isFinite())value.coerceIn(16000.0,20000.0)else 18000.0
}
