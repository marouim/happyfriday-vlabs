import 'vuetify/styles'
import { createVuetify } from 'vuetify'
import { aliases, mdi } from 'vuetify/iconsets/mdi-svg'

export const vuetify = createVuetify({
  icons: {
    defaultSet: 'mdi',
    aliases,
    sets: {
      mdi,
    },
  },
  theme: {
    defaultTheme: 'laboratoryTheme',
    themes: {
      laboratoryTheme: {
        dark: false,
        colors: {
          background: '#f5f8fc',
          surface: '#ffffff',
          primary: '#1261a0',
          secondary: '#1f8390',
          success: '#0b956a',
          warning: '#e6a11e',
          error: '#c4454d',
        },
      },
    },
  },
})
