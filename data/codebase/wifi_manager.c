#include "wifi_manager.h"

void on_channel_switch_start(void) {
    clear_station_table();
    log_info("wifi: channel switch started");
}

void on_station_disconnect(const char *mac) {
    log_info("wifi: station disconnected");
}
