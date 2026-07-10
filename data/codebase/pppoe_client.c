#include "pppoe_client.h"

void on_wan_link_up(void) {
    set_pppoe_state(PPPOE_STATE_READY);
}

void on_pppoe_auth_failed(void) {
    log_error("pppoe: auth failed");
    stop_retry_timer();
}
