<template>
  <div v-if="ui.guideOpen" class="guide-layer">
    <div class="guide-scrim" @click="ui.closeGuide()" />
    <div ref="dialog" class="guide" role="dialog" aria-modal="true" aria-label="使用說明" tabindex="-1">
      <header class="guide-head">
        <h2>使用說明</h2>
        <button class="icon-btn guide-close" aria-label="關閉" @click="ui.closeGuide()"><Icon name="close" /></button>
      </header>

      <div class="guide-body">
        <section class="guide-limits">
          <h3>先知道這個工具做不到什麼</h3>
          <p>
            它能幫你快速縮小研究範圍、看清風險，但不能預測股價，也不保證獲利。
            評分規則尚未經過報酬驗證，歷史表現不代表未來。投入大筆資金前，請自行閱讀財報與公告，必要時諮詢合格顧問。
          </p>
        </section>

        <section>
          <h3>建議流程</h3>
          <ol class="steps">
            <li><b>看環境。</b>總覽的市場狀態與市場寬度。多數股票跌破月線時，好股票也容易下跌，先降低部位。</li>
            <li><b>縮範圍。</b>研究候選清單，或在熱力圖用「穩健優質」等篩選組合。清單是研究起點，不是買進名單。</li>
            <li><b>查原因。</b>點開個股，看哪些基本面條件沒過、排雷項目、法人是否同步。先找不該買的理由。</li>
            <li><b>定部位。</b>進場前先決定停損，用部位試算回推能買多少。大資金特別留意「占 5 日均量」，太高時進出都會推動價格，應分批。</li>
            <li><b>持續追蹤。</b>加入自選並寫下買進理由。跌破均線、法人連賣、出現排雷時，自選警示會提醒你重新檢視。</li>
          </ol>
        </section>

        <section>
          <h3>分散與資金配置</h3>
          <ul class="plain">
            <li>別把大筆資金放在單一股票或單一族群。單檔上限是試算的預設保護，建議不要調高。</li>
            <li>同族群的多檔股票常一起漲跌，看起來分散，實際上是同一筆賭注。</li>
            <li>核心資金可考慮低費用的大盤型 ETF，個股作為衛星配置。</li>
            <li>只投入短期不會用到的錢。</li>
          </ul>
        </section>

        <section>
          <h3>指標怎麼看</h3>
          <dl class="terms">
            <div><dt>買進評分</dt><dd>24 項基本面條件的通過情況，通過率 = 通過項目 ÷ 有資料的項目。</dd></div>
            <div><dt>排雷</dt><dd>現金流、財務等警訊。2 項以上直接列為避開，不論分數多高。</dd></div>
            <div><dt>綜合分</dt><dd>基本面 40%、趨勢 25%、籌碼 20%、評價 15% 的加權，排雷每項扣 10 分。權重是經驗設定，缺資料時不顯示分數。</dd></div>
            <div><dt>研究候選／等回檔</dt><dd>等回檔代表條件不錯但股價離月線超過 10%，追高的風險報酬較差。</dd></div>
            <div><dt>月線／季線</dt><dd>20 日與 60 日均價。站上代表近期買方占優，跌破則相反。</dd></div>
            <div><dt>法人連買</dt><dd>外資加投信連續買超的天數，不含自營商。</dd></div>
            <div><dt>量比</dt><dd>今日成交量 ÷ 前 5 日均量，2 倍以上代表明顯放量。</dd></div>
            <div><dt>P/E 比較</dt><dd>與該股自身近 5 年的本益比區間比較，不是跨產業比較。</dd></div>
          </dl>
        </section>

        <section>
          <h3>卡片上的標記</h3>
          <dl class="legend">
            <div><dt>⚠ 2</dt><dd>排雷項目數</dd></div>
            <div><dt>轉</dt><dd>營收與 EPS 轉強</dd></div>
            <div><dt>估</dt><dd>本益比低於自身歷史</dd></div>
            <div><dt>法 +3</dt><dd>法人連買 3 日（負數為連賣）</dd></div>
            <div><dt>線</dt><dd>站上月線或月季線</dd></div>
            <div><dt>量 ×2.1</dt><dd>量比</dd></div>
            <div><dt>高</dt><dd>接近 52 週高點</dd></div>
          </dl>
        </section>

        <section>
          <h3>資料更新時間</h3>
          <ul class="plain">
            <li>行情：盤中每分鐘，盤後為收盤資料。</li>
            <li>評分、法人、均線：交易日後凌晨 03:00。盤中看到的是前一交易日的結果。</li>
            <li>股價未還原除權息，除息前後的均線與歷史報酬會有落差。</li>
            <li>紅色代表上漲、綠色代表下跌（台股慣例）。</li>
          </ul>
        </section>

        <section>
          <h3>快捷鍵</h3>
          <ul class="plain">
            <li><kbd>/</kbd> 搜尋股票，<kbd>Esc</kbd> 關閉面板，圖表聚焦後用 <kbd>←</kbd> <kbd>→</kbd> 逐日查看。</li>
          </ul>
        </section>
      </div>
    </div>
  </div>
</template>

<script setup>
import { toRef } from 'vue'
import { useUiStore } from '../stores/uiStore'
import { useDialog } from '../composables/useDialog'
import Icon from './Icon.vue'

const ui = useUiStore()
const { dialog } = useDialog(toRef(ui, 'guideOpen'), () => ui.closeGuide())
</script>

<style scoped>
.guide-layer {
  position: fixed;
  inset: 0;
  z-index: 320;
  display: flex;
  align-items: center;
  justify-content: center;
  padding: 16px;
}

.guide-scrim {
  position: absolute;
  inset: 0;
  background: var(--scrim);
}

.guide {
  position: relative;
  display: flex;
  flex-direction: column;
  width: min(680px, 100%);
  max-height: min(84vh, 860px);
  border-radius: var(--radius-lg);
  background: var(--surface);
  border: 1px solid var(--border-default);
  box-shadow: var(--shadow-lg);
  outline: none;
}

.guide-head {
  display: flex;
  align-items: center;
  justify-content: space-between;
  padding: 14px 16px 10px 20px;
  border-bottom: 1px solid var(--border-subtle);
}
.guide-head h2 { font-size: 1.125rem; font-weight: 700; }

.guide-body {
  overflow-y: auto;
  padding: 14px 20px 20px;
  display: flex;
  flex-direction: column;
  gap: 18px;
  font-size: 0.875rem;
  line-height: 1.6;
  color: var(--text-secondary);
}

.guide-body h3 {
  margin-bottom: 4px;
  font-size: 0.9375rem;
  font-weight: 600;
  color: var(--text-primary);
}

.guide-body b { color: var(--text-primary); font-weight: 600; }

.guide-limits {
  padding: 12px 14px;
  border-radius: var(--radius-md);
  background: var(--warn-soft);
}

.steps { padding-left: 1.3em; display: flex; flex-direction: column; gap: 4px; }
.plain { padding-left: 1.2em; display: flex; flex-direction: column; gap: 2px; }

.terms { display: flex; flex-direction: column; gap: 6px; }
.terms dt { font-weight: 600; color: var(--text-primary); }

.legend {
  display: grid;
  grid-template-columns: repeat(auto-fit, minmax(220px, 1fr));
  gap: 2px 16px;
}
.legend div { display: flex; gap: 8px; align-items: baseline; }
.legend dt { flex-shrink: 0; min-width: 3.6em; font-weight: 600; color: var(--text-primary); }

kbd {
  padding: 0 5px;
  border: 1px solid var(--border-default);
  border-radius: 4px;
  font-family: inherit;
  font-size: 0.75rem;
}
</style>
