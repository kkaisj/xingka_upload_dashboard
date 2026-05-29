import { createApp } from "vue";
import { createPinia } from "pinia";
import {
  create,
  NButton,
  NCard,
  NConfigProvider,
  NDataTable,
  NGrid,
  NGridItem,
  NLayout,
  NLayoutContent,
  NLayoutHeader,
  NModal,
  NProgress,
  NScrollbar,
  NSelect,
  NSpace,
  NStatistic,
  NTag,
  NThing,
} from "naive-ui";

import App from "./App.vue";
import "./styles.css";

const naive = create({
  components: [
    NButton,
    NCard,
    NConfigProvider,
    NDataTable,
    NGrid,
    NGridItem,
    NLayout,
    NLayoutContent,
    NLayoutHeader,
    NModal,
    NProgress,
    NScrollbar,
    NSelect,
    NSpace,
    NStatistic,
    NTag,
    NThing,
  ],
});

const app = createApp(App);
app.use(createPinia());
app.use(naive);
app.mount("#app");
