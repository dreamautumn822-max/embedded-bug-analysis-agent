#include "dhcp_server.h"

/* migration keys: lan.dhcp.pool_start lan.dhcp.pool_end */
int restart_dhcp_server(void) {
    if (dhcp_pool_empty()) {
        log_error("dhcpd: lease allocation failed");
        return -1;
    }
    return dhcpd_restart();
}
