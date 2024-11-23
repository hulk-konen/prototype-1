import time
from machine import Pin, I2C
import sys

# Function to check if running from Thonny
def is_running_from_thonny():
    return hasattr(sys.stdin, 'buffer')

# Early interrupt function
def wait_for_interrupt(seconds, button):
    try:
        # Try to set up display for feedback
        i2c = I2C(0, sda=Pin(4), scl=Pin(5), freq=400000)
        display = SSD1306_I2C(128, 64, i2c)
        has_display = True
    except:
        has_display = False

    start_time = time.time()
    while time.time() - start_time < seconds:
        if has_display:
            display.fill(0)
            display.text("Press button to", 0, 0)
            display.text("enter dev mode", 0, 16)
            display.text(f"Time: {seconds - int(time.time() - start_time)}s", 0, 32)
            display.show()

        if button.value() == 0:  # Button pressed
            if has_display:
                display.fill(0)
                display.text("Dev mode", 0, 0)
                display.text("activated!", 0, 16)
                display.show()
            return True
        time.sleep(0.1)
    return False

def main():
    from sim7080_driver import send_at, check_start, set_network, check_network, http_get, http_post
    from ssd1306 import SSD1306_I2C
    import json
    import utime
    from machine import ADC

    # Set up I2C and the pins we're using for it
    i2c = I2C(0, sda=Pin(4), scl=Pin(5), freq=400000)

    # Short delay to stop I2C falling over
    time.sleep(1)

    # Define the display and size (128x64)
    display = SSD1306_I2C(128, 64, i2c)

    last_http_get_time = time.time()  # Initialize the timer

    # LED indicator on Raspberry Pi Pico
    led_pin = 25  # Onboard LED
    led_onboard = Pin(led_pin, Pin.OUT)

    # Analog input for potentiometer
    analog_value = ADC(27)

    # Define pins for the slide switch and tactile button
    SLIDE_SWITCH_PIN = 15  # GPIO pin for the slide switch
    TACTILE_BUTTON_PIN = 16  # GPIO pin for the tactile button

    slide_switch = Pin(SLIDE_SWITCH_PIN, Pin.IN, Pin.PULL_UP)
    tactile_button = Pin(TACTILE_BUTTON_PIN, Pin.IN, Pin.PULL_UP)

    def read_slide_switch():
        return slide_switch.value()  # 0 when switch is ON, 1 when OFF (due to PULL_UP)

    def is_button_pressed():
        return tactile_button.value() == 0  # 0 when button is pressed (due to PULL_UP)

    # Function to blink the LED
    def led_blink():
        for i in range(1, 3):
            led_onboard.value(1)
            utime.sleep(1)
            led_onboard.value(0)
            utime.sleep(1)
        led_onboard.value(0)

    def normalize_reading(reading):
        # Define the sequence of desired values
        mapping = ['00', '10', '11', '12', '13', '14', '15', 
                   '21', '22', '23', '24', '25',
                   '31', '32', '33', '34', '35',
                   '41', '42', '43', '44', '45',
                   '51', '52', '53', '54', '55']

        # Calculate the index based on the input reading
        index = int(reading / 65535 * (len(mapping) - 1))

        # Return the mapped value
        return mapping[index]

    # Main program startup
    display.fill(0)
    display.text("Starting:", 0, 0)
    display.text("Modem ", 0, 12)
    display.show()

    led_blink()
    send_at("AT", "OK")

    display.fill(0)
    display.text("Starting:", 0, 0)
    display.text("Modem started ", 0, 12)
    display.show()

    check_start()

    display.fill(0)
    display.text("Starting:", 0, 0)
    display.text("Network ", 0, 12)
    display.show()

    set_network()

    display.fill(0)
    display.text("Starting:", 0, 0)
    display.text("Checking network ", 0, 12)
    display.show()

    check_network()

    display.fill(0)
    display.text("Starting:", 0, 0)
    display.text("Connected ", 0, 12)
    display.show()

    print("ready")

    while True:
        switch_position = read_slide_switch()

        if switch_position == 0:  # Switch is ON (sending mode)
            reading = analog_value.read_u16()
            normalized_reading = normalize_reading(reading)

            display.fill(0)
            display.text("Send mode:", 0, 0)
            display.text(f"Value: {normalized_reading}", 0, 24)
            display.text("Press to send", 0, 48)
            display.show()

            if is_button_pressed():
                display.fill(0)
                display.text("Send mode:", 0, 0)
                display.text(f"Value: {normalized_reading}", 0, 24)
                display.text("Sending, wait", 0, 48)
                display.show()

                http_post_message = json.dumps({"msg": normalized_reading})
                http_post_response = http_post('http://109.204.233.119:8000', '/post-msg/', http_post_message)

                if http_post_response == 'OK':
                    display.fill(0)
                    display.text("Send mode:", 0, 0)
                    display.text(f"Value: {normalized_reading}", 0, 24)
                    display.text("Message sent", 0, 48)
                    display.show()
                else:
                    display.fill(0)
                    display.text("Send mode:", 0, 0)
                    display.text(f"Value: {normalized_reading}", 0, 24)
                    display.text("Error, try again", 0, 48)
                    display.show()

                time.sleep(2)  # Display the result for 2 seconds

        else:  # Switch is OFF (receiving mode)
            current_time = time.time()

            # Check if 30 seconds have passed since the last http_get call
            if current_time - last_http_get_time >= 30:
                response_body = http_get('http://109.204.233.119:8000', '/latest-text-msg/')

                if response_body:
                    # Process and display the received message
                    start_index = response_body.decode().find('{')
                    end_index = response_body.decode().rfind('}')
                    json_part = response_body.decode()[start_index:end_index+1]
                    print(json_part)
                    try:
                        response_json = json.loads(json_part)
                        message = response_json.get("text_msg")
                        display.fill(0)
                        display.text("Receive mode", 0, 0)
                        display.text(f"Message: {message}", 0, 24)
                        display.show()
                    except (TypeError, ValueError) as e:
                        print(f"Failed to decode JSON response: {e}")
                print("get")
                last_http_get_time = current_time  # Update the timer
            else:
                display.fill(0)
                display.text("Receive mode", 0, 0)
                display.text("Waiting for msgs", 0, 24)
                display.show()

        time.sleep(0.1)  # Small delay to prevent busy-waiting

if __name__ == "__main__":
    # Set up minimal required hardware
    tactile_button = Pin(16, Pin.IN, Pin.PULL_UP)

    # Check if running from Thonny
    if is_running_from_thonny():
        print("Running from Thonny - press button within 5 seconds to interrupt startup")

    # Provide interrupt window
    if wait_for_interrupt(5, tactile_button):
        print("Startup interrupted!")
        print("Device ready for development")
        # Exit without running main program
        sys.exit()
    else:
        # Proceed with normal program execution
        main()
