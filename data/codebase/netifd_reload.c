#include "network.h"

void lan_reload_handler(void) {
    restart_bridge("br-lan");
    restart_dhcp_server();
}

int is_bridge_ready(const char *ifname) {
    return query_link_state(ifname) == LINK_READY;
}
