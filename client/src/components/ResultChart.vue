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
        data,
      }
    ]
  }
})

const chartOptions = computed(() => ({
  responsive: true,
  maintainAspectRatio: false,
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
          const description = props.traitDescriptions[trait];
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
</script>

<template>
  <Radar :data="chartData" :options="chartOptions" />
</template>

<style scoped>
.chart-container {
  position: relative;
  height: 450px;
  width: 100%;
  max-width: 500px;
  margin: 20px auto;
}
</style>
