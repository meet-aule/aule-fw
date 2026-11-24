#include <driver/gpio.h>
#include <esp_app_desc.h>
#include <esp_err.h>
#include <esp_event.h>
#include <esp_log.h>
#include <freertos/FreeRTOS.h>
#include <freertos/task.h>
#include <nvs.h>
#include <nvs_flash.h>

#include "application.h"
#include "aule_git_sha.h"

#define TAG "main"

extern "C" void app_main(void)
{
    // Say what is running before anything else can fail: the version, the commit it was built
    // from and the board. Bug reports quote this line.
    ESP_LOGI(TAG, "Aule firmware %s (%s) on %s", esp_app_get_description()->version, kAuleGitSha,
             BOARD_NAME);

    // Initialize NVS flash for WiFi configuration
    esp_err_t ret = nvs_flash_init();
    if (ret == ESP_ERR_NVS_NO_FREE_PAGES || ret == ESP_ERR_NVS_NEW_VERSION_FOUND) {
        ESP_LOGW(TAG, "Erasing NVS flash to fix corruption");
        ESP_ERROR_CHECK(nvs_flash_erase());
        ret = nvs_flash_init();
    }
    ESP_ERROR_CHECK(ret);

    // Initialize and run the application
    auto& app = Application::GetInstance();
    app.Initialize();
    app.Run();  // This function runs the main event loop and never returns
}
