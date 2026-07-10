#include "tr069_report.h"

int send_periodic_inform(void) {
    const char *acs_host = resolver_cache_get("acs.example.net");
    return http_post_inform(acs_host);
}
