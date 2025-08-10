<script setup>
import { defineProps, computed } from 'vue'
import { Radar } from 'vue-chartjs'
import { Chart as ChartJS, Title, Tooltip, Legend, PointElement, LineElement, RadialLinearScale, Filler } from 'chart.js'

ChartJS.register(Title, Tooltip, Legend, PointElement, LineElement, RadialLinearScale, Filler)

const props = defineProps({
  traitScores: {
    type: Object,
    required: true
  },
  traitDescriptions: {
    type: Object,
    required: true
  }
})

// 特性の定義（フォールバック用）：各項目が「何を意味するか」を簡潔に説明
const fallbackTraitDescriptions = {
  '新規性追求': '未知や型にはまらない体験をどれだけ求めるか（冒険型〜安定志向の連続）。',
  '旅程密度': '1日の予定をどれだけ詰め込むか（行動満載〜余白重視）。',
  '予算哲学': '価格・コスパ重視か、体験の質を優先するか。',
  '社会的志向性': '現地の人／他の旅行者との交流をどれだけ望むか。',
  '主な興味関心': '旅行の中心テーマ（例：グルメ、自然、文化・歴史、リラクゼーション）。',
  '計画志向性': '事前に緻密に計画するか、現地で柔軟に決めるか。',
  '快適性水準': '宿・移動における快適さ・アメニティの重視度。',
  '活動レベル': '旅行中の身体的アクティビティの強度。',
  '安全性の閾値': '治安・医療など安全面をどの程度重視するか。',
  'デジタル統合度': '計画から共有までテクノロジーをどれだけ活用するか。'
}

const getTraitDefinition = (trait) => {
  return props.traitDescriptions?.[trait] || fallbackTraitDescriptions[trait] || ''
}

const chartData = computed(() => {
  if (!props.traitScores) {
    return { labels: [], datasets: [] };
  }
  const labels = Object.keys(props.traitScores);
  const data = Object.values(props.traitScores);
  return {
    labels,
    datasets: [
      {
        label: 'あなたの特性スコア',
        backgroundColor: 'rgba(54, 162, 235, 0.2)',
        borderColor: 'rgb(54, 162, 235)',
        pointBackgroundColor: 'rgb(54, 162, 235)',
        pointBorderColor: '#fff',
        pointHoverBackgroundColor: '#fff',
        pointHoverBorderColor: 'rgb(54, 162, 235)',
        pointRadius: 4,
        pointHoverRadius: 7,
        hitRadius: 14,
        data,
      }
    ]
  }
})

const chartOptions = computed(() => ({
  responsive: true,
  maintainAspectRatio: false,
  interaction: {
    mode: 'nearest',
    intersect: false
  },
  plugins: {
    legend: {
      position: 'top',
    },
    title: {
      display: true,
      text: 'あなたの旅行特性バランス',
      font: {
        size: 20,
        weight: 'bold'
      },
      padding: {
        top: 10,
        bottom: 20
      }
    },
    tooltip: {
      callbacks: {
        label: function(context) {
          let label = context.dataset.label || '';
          if (label) {
            label += ': ';
          }
          if (context.parsed.r !== null) {
            label += context.parsed.r.toFixed(2);
          }
          return label;
        },
         afterLabel: function(context) {
          const trait = context.label;
           const description = getTraitDefinition(trait);
          if (description) {
            // ツールチップ内で改行させるために配列で返す
            const maxLineLength = 30;
            const lines = [];
            let currentLine = '';
            description.split('').forEach(char => {
              if (currentLine.length > maxLineLength && char !== ' '){
                lines.push(currentLine);
                currentLine = '';
              }
              currentLine += char;
            });
            lines.push(currentLine);
            return lines;
          }
          return '';
        }
      },
      bodyFont: {
        size: 14,
      },
      footerFont: {
        size: 12
      },
      displayColors: false,
      backgroundColor: 'rgba(0, 0, 0, 0.8)',
      padding: 10,
    }
  },
  scales: {
    r: {
      angleLines: {
        display: true
      },
      suggestedMin: 0,
      suggestedMax: 4,
      pointLabels: {
        font: {
          size: 14
        }
      },
      ticks: {
        stepSize: 1
      }
    }
  }
}))

const traitsList = computed(() => {
  if (!props.traitScores) return []
  return Object.keys(props.traitScores).map(trait => ({
    trait,
    score: props.traitScores[trait],
  description: getTraitDefinition(trait)
  }))
})
</script>

<template>
  <div class="chart-wrapper">
    <div class="chart-container">
      <Radar :data="chartData" :options="chartOptions" />
    </div>
    <!-- モバイル向け: 項目説明の折りたたみリスト -->
    <div class="mobile-trait-descriptions">
      <h4>各特性（項目）の定義</h4>
      <ul>
        <li v-for="item in traitsList" :key="item.trait">
          <details>
            <summary>
              <span class="trait-name">{{ item.trait }}</span>
              <span class="trait-score">{{ item.score.toFixed(2) }}</span>
            </summary>
            <p class="trait-desc">{{ item.description }}</p>
          </details>
        </li>
      </ul>
    </div>
  </div>
</template>

<style scoped>
.chart-container {
  position: relative;
  height: 520px;
  width: 100%;
  max-width: 720px;
  margin: 20px auto;
}

.chart-container canvas {
  width: 100% !important;
  height: 100% !important;
}

.chart-wrapper {
  position: relative;
}

/* モバイルでのみ表示 */
.mobile-trait-descriptions {
  display: none;
  margin-top: 16px;
}

@media (max-width: 768px) {
  .mobile-trait-descriptions {
    display: block;
  }
  .chart-container {
    height: 460px;
    max-width: 100%;
  }
  .mobile-trait-descriptions ul {
    list-style: none;
    padding: 0;
    margin: 0;
  }
  .mobile-trait-descriptions li + li {
    margin-top: 8px;
  }
  details {
    background: #fff;
    border: 1px solid #e0e0e0;
    border-radius: 8px;
    padding: 10px 12px;
  }
  summary {
    cursor: pointer;
    display: flex;
    justify-content: space-between;
    align-items: center;
    font-weight: 600;
    color: #1a237e;
  }
  .trait-name { margin-right: 8px; }
  .trait-score { color: #555; font-weight: 500; }
  .trait-desc { margin: 10px 2px 4px; line-height: 1.6; }
}
</style>
