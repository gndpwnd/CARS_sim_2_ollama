Arduino GPS modules typically use NMEA sentences to transmit positional data.


RTK GPS modules use RTCM (Radio Technical Commission for Maritime Services) for the high-precision correction data needed for centimeter-level accuracy. They use NMEA (National Marine Electronics Association) for the standard, lower-accuracy GPS data output. 

NMEA 0183

https://www.nmea.org/nmea-0183.html

https://github.com/107-systems/107-Arduino-NMEA-Parser

I want to understand what information is contained in NMEA sentences and RTCM messages. I have a list of constraints and requirements for detecting GPS denial, and i want to understand what constraints and requirements I can monitor using information from NMEA sentences and RTCM messages.


The most current RTCM standard for Differential GNSS (Global Navigation Satellite Systems) is RTCM Standard 10403.4, published on December 1, 2023. This standard introduces significant updates, including compatibility with new GNSS signals, enhanced support for Network RTK, and improved message structures for efficiency and bandwidth optimization, particularly with Multiple Signal Messages (MSM). 



I want an external program to generate random messages when queried. I basically want to make a "satellite constellation" or a python app that generates NMEA sentences and/or RTCM messages when vehicles ask for them.

please use libraries like

https://github.com/semuconsulting/pyrtcm

and 

https://github.com/Knio/pynmea2