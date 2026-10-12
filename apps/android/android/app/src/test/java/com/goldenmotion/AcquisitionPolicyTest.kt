package com.goldenmotion
import org.junit.Test
import org.junit.Assert.*
class AcquisitionPolicyTest {
 @Test fun hostileDurationsAreBounded(){assertEquals(3000L,AcquisitionPolicy.duration(Double.POSITIVE_INFINITY));assertEquals(500L,AcquisitionPolicy.duration(-3.0));assertEquals(5000L,AcquisitionPolicy.duration(100000.0))}
 @Test fun playbackIsLowOutput(){assertEquals(0.01,AcquisitionPolicy.amplitude(10.0),0.0);assertEquals(0.0,AcquisitionPolicy.amplitude(-1.0),0.0)}
 @Test fun toneFrequencyWithinExperimentBand(){assertEquals(18000.0,AcquisitionPolicy.frequency(Double.NaN),0.0);assertEquals(16000.0,AcquisitionPolicy.frequency(-5.0),0.0)}
}
