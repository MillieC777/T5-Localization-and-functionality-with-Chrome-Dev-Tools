# Manual metrics mirror the Chrome DevTools preset values for each device.
# deviceName lookup was dropped — ChromeDriver 148 no longer supports it.
EMULATED_DEVICES = [
    {
        "name":        "pixel_5",
        "width":       393,
        "height":      851,
        "pixel_ratio": 2.75,
        "user_agent":  "Mozilla/5.0 (Linux; Android 11; Pixel 5) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/90.0.4430.91 Mobile Safari/537.36",
    },
    {
        "name":        "samsung_galaxy_s20_ultra",
        "width":       412,
        "height":      915,
        "pixel_ratio": 3.5,
        "user_agent":  "Mozilla/5.0 (Linux; Android 10; SM-G981B) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/80.0.3987.162 Mobile Safari/537.36",
    },
]
