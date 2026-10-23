-keep class org.jtransforms.** { *; }
-keep class pl.edu.icm.jlargearrays.** { *; }
-dontwarn sun.misc.Unsafe
-dontwarn java.lang.management.**
-dontwarn javax.management.**
# JLargeArrays' optional >2^31-element/object-serialization paths reference
# desktop-JDK-only classes. Our FFTs use small ordinary FloatArrays exclusively.
-dontwarn sun.misc.Cleaner
-dontwarn com.sun.xml.internal.ws.encoding.soap.SerializationException
